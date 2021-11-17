import asyncio
from configparser import NoSectionError, NoOptionError, SafeConfigParser
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from backup_tool.exception import CLIException
from backup_tool.client import BackupClient
from backup_tool.cli.common import CommonArgparse
from backup_tool.database import BackupEntryLocalFile

HOME_PATH = Path(os.path.expanduser('~'))
DEFAULT_SETTINGS_FILE = HOME_PATH/ '.backup-tool' / 'config'

class ClientCLI():
    '''
    CLI for Backup Client
    '''
    def __init__(self, **kwargs):
        '''
        Backup Client
        '''
        crypto_key = kwargs.pop('crypto_key_file', None)
        if crypto_key:
            key_file_path = Path(crypto_key)
            if key_file_path.exists():
                crypto_key = key_file_path.read_text().strip() #pylint:disable=unspecified-encoding

        self.temporary_directory = TemporaryDirectory() #pylint:disable=consider-using-with

        client_kwargs = {
            'database_file': kwargs.pop('database_file', None),
            'crypto_key': crypto_key,
            'work_directory': kwargs.pop('work_directory', self.temporary_directory.name),
            'logging_file': kwargs.pop('logging_file', None),
            'relative_path': kwargs.pop('relative_path', None),

            'oci_config_file': kwargs.pop('oci_config_file', None),
            'oci_config_section': kwargs.pop('oci_config_section', None),
            'oci_namespace': kwargs.pop('oci_namespace', None),
            'oci_bucket': kwargs.pop('oci_bucket', None),
        }

        self.client = BackupClient(**client_kwargs)
        self.command_str = f'{kwargs.pop("module")}_{kwargs.pop("command")}'
        self.additional_kwargs = kwargs
        # Cache file may be given later in some functions
        self.cache_file = None
        self.cache_json = {
            'backup': {
                'pending_upload': {},
                'processed': [],
            },
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.cache_file and self.cache_json:
            self.cache_file.write_text(json.dumps(self.cache_json))
        temp_dir_path = Path(self.temporary_directory.name)
        for child in temp_dir_path.glob('*'):
            if child.is_file():
                child.unlink()
        temp_dir_path.rmdir()

    async def run_command(self):
        '''
        Run command given in kwargs
        '''
        try:
            command = getattr(self, self.command_str)
            value = await command(**self.additional_kwargs)
        except AttributeError:
            command = getattr(self.client, self.command_str)
            value = command(**self.additional_kwargs)
        if value is not None:
            print(json.dumps(value, indent=4))

    async def __produce_backup_files(self, directory_queue, backup_queue, skip_files, file_names_pending_upload, thread_count):
        self.client.logger.debug(f'Starting backkup producer thread {thread_count}')
        while True:
            directory_path = await directory_queue.get()
            self.client.logger.info(f'Generating file list from directory "{str(directory_path)}"')
            for file_path in directory_path.glob('**/*'):
                file_name = file_path.resolve()
                # Skip if matches any continue
                skip = False
                for skip_check in skip_files:
                    if re.match(skip_check, file_name):
                        self.client.logger.warning(f'Ignoring file "{file_name}" since matches skip check "{skip_check}"')
                        skip = True
                        break
                if skip:
                    continue
                if file_name in self.cache_json['backup']['processed'] or file_name in file_names_pending_upload:
                    self.client.logger.debug(f'Ignoring file "{file_name}" as it is in cache or pending upload')
                    continue
                if file_name.is_dir():
                    continue
                self.client.logger.debug(f'Adding file to backup queue "{file_name}"')
                await backup_queue.put(file_name)
            directory_queue.task_done()
            await asyncio.sleep(1)

    async def __consume_backup_files(self, backup_queue, upload_queue, overwrite, check_uploaded_md5, thread_count):
        self.client.logger.debug(f'Starting backup consumer thread {thread_count}')
        while True:
            file_name = await backup_queue.get()
            self.client.logger.debug(f'Backup consumer thread {thread_count}, backing up file {file_name}')
            upload_data = self.client.file_backup(file_name, overwrite=overwrite, check_uploaded_md5=check_uploaded_md5, automatically_upload_files=False)
            if upload_data == {}:
                self.cache_json['backup']['processed'].append(file_name)
            else:
                upload_data_key = upload_data.pop('local_file')
                self.cache_json['backup']['pending_upload'][upload_data_key] = upload_data
                await upload_queue.put(upload_data)
            backup_queue.task_done()
            await asyncio.sleep(1)

    async def __consume_upload_files(self, upload_queue, thread_count):
        self.client.logger.debug(f'Starting upload consumer thread {thread_count}')
        while True:
            upload_data = await upload_queue.get()
            local_backup_file = self.client.db_session.query(BackupEntryLocalFile).get(upload_data['local_backup_file_id'])
            self.client.logger.debug(f'Upload consumer thread {thread_count}, uploading crypto of file {str(upload_data["local_file"])}')
            try:
                object_path = self.cache_json['backup']['pending_upload'][upload_data['local_file']]['object_path']
            except KeyError:
                object_path = self.client._generate_uuid()
                self.cache_json['backup']['pending_upload'][upload_data['local_file']]['object_path'] = object_path
            self.client._file_backup_upload(upload_data['crypto_file'], #pylint:disable=protected-access
                                            upload_data['crypto_file_md5'],
                                            upload_data['offset'],
                                            local_backup_file,
                                            object_path=object_path)
            self.cache_json['backup']['processed'].append(str(upload_data['local_file']))
            del self.cache_json['backup']['pending_upload'][upload_data['local_file']]
            upload_queue.task_done()
            await asyncio.sleep(1)

    async def directory_backup(self, dir_paths, overwrite=False, #pylint:disable=too-many-locals
                        check_uploaded_md5=False, skip_files=None,
                        cache_file=None):
        '''
        Backup all files in directory

        dir_paths           :       Directories to backup
        overwrite           :       Upload new file is md5 is changed
        check_uploaded_md5  :       Ensure any existing backup file matches expected encryption
        skip_files          :       List of regexes to ignore for backup
        cache_file          :       Cache File Location, will use default in work directory otherwise
        '''
        # Read cached information if its there
        self.cache_file = cache_file or self.client.work_directory / 'cache_file.json'
        if self.cache_file.exists():
            self.cache_json = json.loads(self.cache_file.read_text())

        directory_queue = asyncio.Queue()
        for dir_path in dir_paths:
            directory_path = Path(dir_path).resolve()
            if not directory_path.exists():
                self.client.logger.error(f'Unable to find directory {str(directory_path)}')
                return
            await directory_queue.put(directory_path)

        # Make sure skip files is a string type
        if skip_files is None:
            skip_files = []
        elif isinstance(skip_files, str):
            skip_files = [skip_files]

        backup_queue = asyncio.Queue()
        upload_queue = asyncio.Queue()
        # Check files that need to be uploaded still
        file_names_pending_upload = []
        for local_file, upload_data in self.cache_json['backup']['pending_upload'].items():
            upload_data['local_file'] = local_file
            await upload_queue.put(upload_data)
            file_names_pending_upload.append(local_file)

        self.client.logger.debug('Generating upload file consumer queues')
        upload_consumers = [asyncio.create_task(self.__consume_upload_files(upload_queue,  count)) for count in range(1)]
        self.client.logger.debug('Generating backup file consumer queues')
        backup_consumers = [asyncio.create_task(self.__consume_backup_files(backup_queue, upload_queue, overwrite, check_uploaded_md5, count)) for count in range(3)]
        self.client.logger.debug('Generating backup file producer queues')
        producers = [asyncio.create_task(self.__produce_backup_files(directory_queue, backup_queue, skip_files, file_names_pending_upload, count)) for count in range(1)]
        self.client.logger.debug('Waiting for all threads to complete')
        await asyncio.wait(producers + backup_consumers + upload_consumers)

def parse_args(args): #pylint:disable=too-many-locals,too-many-statements
    '''
    Parse command line args
    '''
    parser = CommonArgparse(description='Backup Tool CLI')
    parser.add_argument('-s', '--settings-file', default=str(DEFAULT_SETTINGS_FILE),
                        help='Settings file')
    parser.add_argument('-d', '--database-file', help='Client sqlite database file')
    parser.add_argument('-l', '--logging-file', help='Logging file')
    parser.add_argument('-k', '--crypto-key-file', help='Cryto key file')
    parser.add_argument('-r', '--relative-path', help='Relative file path')
    parser.add_argument('-w', '--work-directory', help='Work directory for temp files')

    parser.add_argument('-c', '--oci-config-file', help='OCI Config File')
    parser.add_argument('-cs', '--oci-config-section', help='OCI Config Stage')
    parser.add_argument('-n', '--oci-namespace', help='Object storage namespace')
    parser.add_argument('-b', '--oci-bucket', help='Object storage bucket')


    # Sub parsers
    sub_parser = parser.add_subparsers(dest='module', description='Sub-modules')
    file_parser = sub_parser.add_parser('file', help='File Module')
    backup_parser = sub_parser.add_parser('backup', help='Backup Module')
    dir_parser = sub_parser.add_parser('directory', help='Directory Module')

    # File Arguments
    file_sub_parser = file_parser.add_subparsers(dest='command', description='Command')

    # File List
    file_sub_parser.add_parser('list', help='List files')

    # File duplicates
    file_sub_parser.add_parser('duplicates', help='Find duplicate files')

    # File cleanup
    file_cleanup = file_sub_parser.add_parser('cleanup', help='Delete files from database no longer present on filesystem')
    file_cleanup.add_argument('--dry-run', '-d', action='store_true', help='Do not delete files')

    # File backup
    file_backup = file_sub_parser.add_parser('backup', help='Backup file')
    file_backup.add_argument('local_file', help='Local file path')
    file_backup.add_argument('--overwrite', '-o', action='store_true', help='Overwrite copy in database')
    file_backup.add_argument('--check-uploaded-md5', '-m', action='store_true', help='Check uploaded md5 matches expected')

    # File restore
    file_restore = file_sub_parser.add_parser('restore', help='Restore from backup file')
    file_restore.add_argument('local_file_id', type=int, help='Local file id')
    file_restore.add_argument('--overwrite', '-o', action='store_true', help='Overwrite copy locally')
    file_restore.add_argument('--set-restore', '-sr', action='store_true', help='Attempt to restore archived files')

    # File md5
    file_md5 = file_sub_parser.add_parser('md5', help='Get md5 sum of file, in base64 encoding')
    file_md5.add_argument('local_file', help='Local file path')

    # File encrypt
    file_encrypt = file_sub_parser.add_parser('encrypt', help='Encrypt local file, but do not upload')
    file_encrypt.add_argument('local_input_file', help='Local input file')
    file_encrypt.add_argument('local_output_file', help='Local output file')

    # File decrypt
    file_decrypt = file_sub_parser.add_parser('decrypt', help='Decrypt local file')
    file_decrypt.add_argument('local_input_file', help='Local input file')
    file_decrypt.add_argument('local_output_file', help='Local output file')
    file_decrypt.add_argument('offset', type=int, help='Offset of decryption')

    # Backup Arguments
    backup_sub_parser = backup_parser.add_subparsers(dest='command', description='Command')

    # Backup List
    backup_sub_parser.add_parser('list', help='List backups')

    # Backup cleanup
    backup_cleanup = backup_sub_parser.add_parser('cleanup', help='Delete backups from database and object storage that dont have local files')
    backup_cleanup.add_argument('--dry-run', '-d', action='store_true', help='Do not delete these backups')

    # Directory Arguments
    dir_sub_parser = dir_parser.add_subparsers(dest='command', description='Command')

    # Directory backup
    dir_backup = dir_sub_parser.add_parser('backup', help='Backup file')
    dir_backup.add_argument('dir_paths', nargs='+', help='Directory local path')
    dir_backup.add_argument('--overwrite', '-o', action='store_true', help='Overwrite copy in database')
    dir_backup.add_argument('--check-uploaded-md5', '-m', action='store_true', help='Check uploaded md5 matches expected')
    dir_backup.add_argument('--skip-files', '-f', nargs='+', help='Skip files matching regexes')
    dir_backup.add_argument('--cache-file', '-cf', help='Cache file to use for directory backup')

    # Final Steps
    parsed_args = vars(parser.parse_args(args))

    if not parsed_args['module']:
        raise CLIException("Missing args: No module provided")

    if not parsed_args['command']:
        raise CLIException("Missing args: No command provided")

    return parsed_args

def load_settings(settings_file):
    '''
    Load settings from file
    '''
    if settings_file is None:
        return {}
    parser = SafeConfigParser()
    parser.read(settings_file)
    mapping = {
        'database_file' : ['general', 'database_file'],
        'logging_file' : ['general', 'logging_file'],
        'crypto_key_file' : ['general', 'crypto_key_file'],
        'relative_path' : ['general', 'relative_path'],

        'oci_namespace' : ['oci', 'namespace'],
        'oci_bucket' : ['oci', 'bucket'],
        'oci_config_file' : ['oci', 'config_file'],
        'oci_config_section' : ['oci', 'config_section'],
    }
    return_data = {}
    for key_name, args in mapping.items():
        try:
            value = parser.get(*args)
            return_data[key_name] = value
        except (NoSectionError, NoOptionError):
            pass
    return return_data

def generate_args(command_line_args):
    '''
    Generate client args from cli and settings file

    Any argument given via cli will override one from settings file
    '''
    cli_args = parse_args(command_line_args)
    args = load_settings(cli_args.pop('settings_file', None))
    override_args = {}
    for k, v in cli_args.items():
        if v is not None:
            override_args[k] = v
    args.update(override_args)
    return args

async def main_runner():
    '''
    Main Runner
    '''
    try:
        args = generate_args(sys.argv[1:])
        with ClientCLI(**args) as client_cli:
            await client_cli.run_command()
    except CLIException as error:
        print(str(error))

def main():
    '''
    Actual main method
    '''
    asyncio.run(main_runner())
