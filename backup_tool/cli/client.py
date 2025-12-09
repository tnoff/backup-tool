import json
import os
import re
import sys
from tempfile import TemporaryDirectory

from pathlib import Path
from yaml import safe_load
from yaml.parser import ParserError

from backup_tool.exception import CLIException
from backup_tool.client import BackupClient
from backup_tool.cli.common import CommonArgparse
from backup_tool.database import BackupEntryLocalFile
from backup_tool import utils

HOME_PATH = Path(os.path.expanduser('~'))
DEFAULT_SETTINGS_FILE = HOME_PATH / '.backup-tool' / 'config'

class ClientCLI():
    '''
    CLI for Backup Client
    '''
    def __init__(self, **kwargs):
        '''
        Backup Client
        '''
        general_config = kwargs.pop('general', {})
        oci_config = kwargs.pop('oci', {})

        crypto_key = general_config.pop('crypto_key_file', None)
        if crypto_key:
            key_file_path = Path(crypto_key)
            if key_file_path.exists():
                crypto_key = key_file_path.read_text().strip() #pylint:disable=unspecified-encoding
            else:
                raise CLIException(f'Crypto key file {crypto_key} does not exist')

        self.temporary_directory = TemporaryDirectory() #pylint:disable=consider-using-with

        client_kwargs = {
            'database_file': general_config.pop('database_file', None),
            'crypto_key': crypto_key,
            'work_directory': general_config.pop('work_directory', self.temporary_directory.name),
            'logging_file': general_config.pop('logging_file', None),
            'relative_path': general_config.pop('relative_path', None),

            'oci_config_file': oci_config.pop('config_file', None),
            'oci_config_section': oci_config.pop('config_section', None),
            'oci_instance_principal': oci_config.pop('instance_principal', None),
            'oci_namespace': oci_config.pop('namespace', None),
            'oci_bucket': oci_config.pop('bucket', None),
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

    def run_command(self):
        '''
        Run command given in kwargs
        '''
        try:
            command = getattr(self, self.command_str)
            value = command(**self.additional_kwargs)
        except AttributeError:
            command = getattr(self.client, self.command_str)
            value = command(**self.additional_kwargs)
        if value is not None:
            print(json.dumps(value, indent=4))

    def __consume_backup_file(self, local_file_path, overwrite, force_checksum=False):
        self.client.logger.debug(f'Backup up file {str(local_file_path)}')

        # Get relative path for database
        relative_file_path = local_file_path
        if self.client.relative_path:
            relative_file_path = local_file_path.relative_to(self.client.relative_path)

        # Get database entry to check metadata
        local_backup_file = self.client.db_session.query(BackupEntryLocalFile).\
            filter(BackupEntryLocalFile.local_file_path == str(relative_file_path)).first()

        # Check metadata first (unless force_checksum)
        if local_backup_file and not force_checksum:
            if not self.client._check_metadata_changed(local_file_path, local_backup_file): #pylint:disable=protected-access
                # Metadata unchanged - file likely hasn't changed
                if local_backup_file.backup_entry_id:
                    self.client.logger.debug(f'File metadata unchanged, skipping backup for "{str(local_file_path)}"')
                    self.cache_json['backup']['processed'].append(str(local_file_path))
                    return None

        local_file_md5 = utils.md5(local_file_path)
        self.client.logger.debug(f'Local file "{str(local_file_path)}" has md5 {local_file_md5}')
        should_upload_file, local_backup_file = self.client._file_backup_ensure_database_entry(local_file_path, #pylint:disable=protected-access
                                                                                                local_file_md5,
                                                                                                overwrite)
        if not should_upload_file:
            # Update metadata cache even if not uploading (md5 matched but metadata changed)
            self.client._update_metadata_cache(local_file_path, local_backup_file) #pylint:disable=protected-access
            self.cache_json['backup']['processed'].append(str(local_file_path))
            return None
        encryption_data = self.client._file_backup_encrypt(local_file_path, local_file_md5) #pylint:disable=protected-access
        encryption_data_key = encryption_data.get('local_file')
        encryption_data['local_backup_file_id'] = local_backup_file.id
        self.cache_json['backup']['pending_upload'][encryption_data_key] = encryption_data
        return encryption_data

    def __consume_upload_files(self, encryption_data):
        self.client.logger.debug(f'Uploading crypto of file {str(encryption_data["local_file"])}')
        local_backup_file = self.client.db_session.get(BackupEntryLocalFile, encryption_data['local_backup_file_id'])
        resume_upload = False
        try:
            object_path = self.cache_json['backup']['pending_upload'][encryption_data['local_file']]['object_path']
            resume_upload = True
        except KeyError:
            object_path = self.client._generate_uuid() #pylint:disable=protected-access
            self.cache_json['backup']['pending_upload'][encryption_data['local_file']]['object_path'] = object_path
        self.client._file_backup_upload(encryption_data['encrypted_file'], #pylint:disable=protected-access
                                        encryption_data['encrypted_file_md5'],
                                        encryption_data['local_file_md5'],
                                        local_backup_file,
                                        object_path=object_path,
                                        resume_upload=resume_upload)
        # Update metadata cache after successful upload
        self.client._update_metadata_cache(Path(encryption_data['local_file']), local_backup_file) #pylint:disable=protected-access
        self.cache_json['backup']['processed'].append(str(encryption_data['local_file']))
        del self.cache_json['backup']['pending_upload'][encryption_data['local_file']]
        Path(encryption_data['encrypted_file']).unlink()

    def directory_backup(self, dir_paths, overwrite=False, #pylint:disable=too-many-locals
                        skip_files=None, cache_file=None, force_checksum=False):
        '''
        Backup all files in directory

        dir_paths           :       Directories to backup
        overwrite           :       Upload new file if md5 has changed
        skip_files          :       List of regexes to ignore for backup
        cache_file          :       Cache File Location, will use default in work directory otherwise
        force_checksum      :       Force MD5 calculation even if metadata unchanged
        '''
        # Read cached information if its there
        self.cache_file = Path(cache_file).expanduser() if cache_file else self.client.work_directory / 'cache_file.json'
        if self.cache_file.exists():
            self.cache_json = json.loads(self.cache_file.read_text())

        directory_list = []
        for dir_path in dir_paths:
            directory_path = Path(dir_path).resolve()
            if not directory_path.exists():
                self.client.logger.error(f'Unable to find directory {str(directory_path)}')
                return
            directory_list.append(directory_path)

        # Make sure skip files is a string type
        if skip_files is None:
            skip_files = []
        elif isinstance(skip_files, str):
            skip_files = [skip_files]

        self.client.logger.debug('Generating backup file producer queues')
        # Keep a list here, since cache json will be effected during upload
        pending_encryption_dicts = []
        for local_file, encryption_data in self.cache_json['backup']['pending_upload'].items():
            encryption_data['local_file'] = local_file
            pending_encryption_dicts.append(encryption_data)

        for encryption_data in pending_encryption_dicts:
            self.__consume_upload_files(encryption_data)

        pending_backup_files = []
        for directory_path in directory_list:
            self.client.logger.info(f'Generating file list from directory "{str(directory_path)}"')
            for file_name in directory_path.glob('**/*'):
                file_path = file_name.resolve()
                # Skip if matches any continue
                skip = False
                for skip_check in skip_files:
                    if re.match(skip_check, str(file_path)):
                        self.client.logger.warning(f'Ignoring file "{str(file_path)}" since matches skip check "{skip_check}"')
                        skip = True
                        break
                if skip:
                    continue

                if str(file_path) in self.cache_json['backup']['processed']:
                    self.client.logger.debug(f'Ignoring file "{str(file_path)}" as it is in cache or pending upload')
                    continue
                if file_name.is_dir():
                    continue
                if file_name.is_symlink():
                    self.client.logger.warning(f'Ignoring symlink file {str(file_name)}')
                    continue
                self.client.logger.debug(f'Adding file to backup queue "{str(file_path)}"')
                pending_backup_files.append(file_path)

        for local_file_path in pending_backup_files:
            # Check if file is within relative_path before processing
            encryption_data = self.__consume_backup_file(local_file_path, overwrite, force_checksum)
            if encryption_data:
                self.__consume_upload_files(encryption_data)
        self.client.logger.debug('Generating upload file consumer queues')


def parse_args(args): #pylint:disable=too-many-locals,too-many-statements
    '''
    Parse command line args
    '''
    parser = CommonArgparse(description='Backup Tool CLI')
    parser.add_argument('-s', '--settings-file', default=str(DEFAULT_SETTINGS_FILE),
                        help='Settings file')


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
    file_backup.add_argument('--force-checksum', '-fc', action='store_true',
                            help='Force full MD5 checksum calculation even if file metadata (mtime/size) unchanged')

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
    dir_backup.add_argument('--dir-paths', nargs='+', required=True, help='Directory local path')
    dir_backup.add_argument('--overwrite', '-o', action='store_true', help='Overwrite copy in database')
    dir_backup.add_argument('--skip-files', '-f', nargs='+', help='Skip files matching regexes')
    dir_backup.add_argument('--cache-file', '-cf', help='Cache file to use for directory backup')
    dir_backup.add_argument('--force-checksum', '-fc', action='store_true',
                           help='Force full MD5 checksum calculation even if file metadata (mtime/size) unchanged')

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
    with open(settings_file, 'r', encoding='utf-8') as reader:
        try:
            return safe_load(reader) or {}
        except ParserError:
            return {}

def generate_args(command_line_args):
    '''
    Generate client args from cli and settings file

    Any argument given via cli will override one from settings file
    '''
    cli_args = parse_args(command_line_args)
    settings = load_settings(cli_args.pop('settings_file', None))
    settings.update(cli_args)
    return settings

def main():
    '''
    Main Runner
    '''
    try:
        args = generate_args(sys.argv[1:])
        with ClientCLI(**args) as client_cli:
            client_cli.run_command()
    except CLIException as error:
        print(str(error))
