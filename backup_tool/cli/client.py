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
                'pending': [],
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
        except AttributeError:
            command = getattr(self.client, self.command_str)
        value = command(**self.additional_kwargs)
        if value is not None:
            print(json.dumps(value, indent=4))

    def directory_backup(self, dir_path, overwrite=False,
                        check_uploaded_md5=False, skip_files=None,
                        cache_file=None):
        '''
        Backup all files in directory

        local_file          :       Full path of local file
        overwrite           :       Upload new file is md5 is changed
        check_uploaded_md5  :       Ensure any existing backup file matches expected encryption
        skip_files          :       List of regexes to ignore for backup
        cache_file          :       Cache File Location, will use default in work directory otherwise
        '''
        # Read cached information if its there
        self.cache_file = cache_file or self.client.work_directory / 'cache_file.json'
        if self.cache_file.exists():
            self.cache_json = json.loads(self.cache_file.read_text())

        directory_path = Path(dir_path).resolve()
        if not directory_path.exists():
            self.client.logger.error(f'Unable to find directory {str(directory_path)}')
            return

        # Make sure skip files is a string type
        if skip_files is None:
            skip_files = []
        elif isinstance(skip_files, str):
            skip_files = [skip_files]

        file_list = []

        self.client.logger.info(f'Generating file list from directory "{str(directory_path)}"')
        for file_name in directory_path.glob('**/*'):
            # Skip if matches any continue
            skip = False
            for skip_check in skip_files:
                if re.match(skip_check, str(file_name)):
                    self.client.logger.warning(f'Ignoring file "{str(file_name)}" since matches skip check "{skip_check}"')
                    skip = True
                    break
            if skip:
                continue
            if str(file_name) in self.cache_json['backup']['processed']:
                self.client.logger.warning(f'Ignoring file "{str(file_name)}" as it is in cache')
                continue
            if file_name.is_dir():
                continue
            self.client.logger.debug(f'Adding file to backup queue "{str(file_name)}"')
            file_list.append(file_name)

        for file_name in file_list:
            self.client.file_backup(str(file_name), overwrite=overwrite, check_uploaded_md5=check_uploaded_md5)
            self.cache_json['backup']['processed'].append(str(file_name))

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
    dir_backup.add_argument('dir_path', help='Directory local path')
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
