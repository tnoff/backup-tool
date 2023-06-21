import json
import os
import sys
from tempfile import TemporaryDirectory

from pathlib import Path
from yaml import safe_load
from yaml.parser import ParserError

from backup_tool.exception import CLIException
from backup_tool.client import BackupClient
from backup_tool.cli.common import CommonArgparse

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
            'storage_option': general_config.pop('storage_option', None),
        }

        client_kwargs['storage_kwargs'] = {}
        if oci_config:
            client_kwargs['storage_kwargs'] = {
                'config_file': oci_config.pop('config_file', None),
                'config_section': oci_config.pop('config_section', None),
                'instance_principal': oci_config.pop('instance_principal', None),
                'bucket_name': oci_config.pop('bucket_name', None),
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
