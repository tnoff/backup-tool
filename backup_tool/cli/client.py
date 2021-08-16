#!/usr/bin/env python
from configparser import NoSectionError, NoOptionError, SafeConfigParser
import json
import os
import sys

from backup_tool.exception import CLIException
from backup_tool.client import BackupClient
from backup_tool.cli.common import CommonArgparse

DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser('~'),
                                   '.oci',
                                   'config')

DEFAULT_CLIENT_PATH = os.path.join(os.path.expanduser('~'), '.backup-tool')

if not os.path.isdir(DEFAULT_CLIENT_PATH):
    os.makedirs(DEFAULT_CLIENT_PATH)

DEFAULT_SETTINGS_FILE = os.path.join(DEFAULT_CLIENT_PATH, 'config')


class ClientCLI():
    '''
    CLI for Backup Client
    '''
    def __init__(self, **kwargs):
        '''
        Backup Client
        '''
        # Read crytpo key from file
        key_file = kwargs.pop('crypto_key_file')
        with open(key_file, 'r') as key_reader:
            crypto_key = key_reader.read().strip()

        with BackupClient(kwargs.pop('database_file'),
                                   crypto_key,
                                   kwargs.pop('config_file'),
                                   kwargs.pop('config_stage'),
                                   kwargs.pop('namespace'),
                                   kwargs.pop('bucket_name'),
                                   logging_file=kwargs.pop('log_file'),
                                   relative_path=kwargs.pop('relative_path'),
                                   work_directory=kwargs.pop('work_directory')
                                   ) as self.client:
            command = getattr(self.client,
                            "%s_%s" % (kwargs.pop('module'), kwargs.pop('command')))
            value = command(**kwargs)
            if value is not None:
                print(json.dumps(value, indent=4))

def parse_args(args): #pylint:disable=too-many-locals,too-many-statements
    '''
    Parse command line args
    '''
    parser = CommonArgparse(description="Client CLI")
    parser.add_argument("-s", "--settings-file", default=DEFAULT_SETTINGS_FILE,
                        help="Settings file")

    parser.add_argument("-c", "--config-file",
                        help="OCI Config File")
    parser.add_argument("-cs", "--config-stage",
                        help="OCI Config Stage")
    parser.add_argument("-d", "--database-file",
                        help="Client sqlite database file")
    parser.add_argument("-l", "--log-file",
                        help="Logging file")
    parser.add_argument("-k", "--crypto-key-file", help="Cryto key")
    parser.add_argument("-r", "--relative-path", help="Relative file path")
    parser.add_argument("-n", "--namespace",
                        help="Object storage namespace")
    parser.add_argument("-b", "--bucket-name",
                        help="Object storage bucket")
    parser.add_argument('-w', '--work-directory',
                        help='Work directory for temp files')


    # Sub parsers
    sub_parser = parser.add_subparsers(dest="module", description="Sub-modules")
    file_parser = sub_parser.add_parser("file", help="File Module")
    backup_parser = sub_parser.add_parser("backup", help="Backup Module")
    dir_parser = sub_parser.add_parser("directory", help="Directory Module")

    # File Arguments
    file_sub_parser = file_parser.add_subparsers(dest="command", description="Command")

    # File List
    file_sub_parser.add_parser("list", help="List files")

    # File duplicates
    file_sub_parser.add_parser("duplicates", help="Find duplicate files")

    # File cleanup
    file_cleanup = file_sub_parser.add_parser("cleanup", help="Delete files from database no longer present on filesystem")
    file_cleanup.add_argument("--dry-run", "-d", action="store_true", help="Do not delete files")

    # File backup
    file_backup = file_sub_parser.add_parser("backup", help="Backup file")
    file_backup.add_argument("local_file", help="Local file path")
    file_backup.add_argument("--overwrite", "-o", action="store_true", help="Overwrite copy in database")
    file_backup.add_argument("--check-uploaded-md5", "-c", action="store_true", help="Check uploaded md5 matches expected")

    # File restore
    file_restore = file_sub_parser.add_parser("restore", help="Restore from backup file")
    file_restore.add_argument("local_file_id", help="Local file id")
    file_restore.add_argument("--overwrite", "-o", action="store_true", help="Overwrite copy locally")
    file_restore.add_argument("--set-restore", "-r", action="store_true", help="Attempt to restore archived files")

    # File md5
    file_md5 = file_sub_parser.add_parser("md5", help="Get md5 sum of file, in base64 encoding")
    file_md5.add_argument("local_file", help="Local file path")

    # File encrypt
    file_encrypt = file_sub_parser.add_parser("encrypt", help="Encrypt local file, but do not upload")
    file_encrypt.add_argument("local_input_file", help="Local input file")
    file_encrypt.add_argument("local_output_file", help="Local output file")

    # File decrypt
    file_decrypt = file_sub_parser.add_parser("decrypt", help="Decrypt local file")
    file_decrypt.add_argument("local_input_file", help="Local input file")
    file_decrypt.add_argument("local_output_file", help="Local output file")
    file_decrypt.add_argument("offset", type=int, help="Offset of decryption")

    # Backup Arguments
    backup_sub_parser = backup_parser.add_subparsers(dest="command", description="Command")

    # Backup List
    backup_sub_parser.add_parser("list", help="List backups")

    # Backup cleanup
    backup_cleanup = backup_sub_parser.add_parser("cleanup", help="Delete backups from database and object storage that dont have local files")
    backup_cleanup.add_argument("--dry-run", "-d", action="store_true", help="Do not delete these backups")

    # Directory Arguments
    dir_sub_parser = dir_parser.add_subparsers(dest="command", description="Command")

    # Directory backup
    dir_backup = dir_sub_parser.add_parser("backup", help="Backup file")
    dir_backup.add_argument("dir_path", help="Directory local path")
    dir_backup.add_argument("--overwrite", "-o", action="store_true", help="Overwrite copy in database")
    dir_backup.add_argument("--check-uploaded-md5", "-c", action="store_true", help="Check uploaded md5 matches expected")
    dir_backup.add_argument("--skip-files", "-s", nargs="+", help="Skip files matching regexes")

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
        'log_file' : ['general', 'logging_file'],
        'crypto_key_file' : ['general', 'crypto_key_file'],
        'relative_path' : ['general', 'relative_path'],
        'namespace' : ['object_storage', 'namespace'],
        'bucket_name' : ['object_storage', 'bucket_name'],
        'config_file' : ['oci', 'config_file'],
        'config_stage' : ['oci', 'config_stage'],
    }
    return_data = dict()
    for key_name, args in mapping.items():
        try:
            value = parser.get(*args)
        except (NoSectionError, NoOptionError):
            value = None
        return_data[key_name] = value
    return return_data


def generate_args(command_line_args):
    '''
    Generate client args from cli and settings file

    Any argument given via cli will override one from settings file
    '''
    cli_args = parse_args(command_line_args)
    args = load_settings(cli_args.pop('settings_file', None))

    args_to_pop = []
    for k, v in cli_args.items():
        if v is None:
            args_to_pop.append(k)
    for k in args_to_pop:
        cli_args.pop(k)
    args.update(cli_args)

    return args

def main():
    '''
    Main Runner
    '''
    try:
        args = generate_args(sys.argv[1:])
        ClientCLI(**args)
    except CLIException as error:
        print(str(error))
