from copy import deepcopy

import pytest

from backup_tool.cli.client import DEFAULT_SETTINGS_FILE, parse_args
from backup_tool.exception import CLIException

def test_parse_args_exceptions():
    with pytest.raises(CLIException) as error:
        parse_args([])
    assert str(error.value) == 'Missing args: No module provided'

    with pytest.raises(CLIException) as error:
        parse_args(['file'])
    assert str(error.value) == 'Missing args: No command provided'

def test_global_args():
    args = parse_args(['-s', 'settings.conf', 'file', 'list'])
    assert args.pop('settings_file') == 'settings.conf'
    args = parse_args(['--settings-file', 'settings.conf', 'file', 'list'])
    assert args.pop('settings_file') == 'settings.conf'

    args = parse_args(['-d', 'db.sql', 'file', 'list'])
    assert args.pop('database_file') == 'db.sql'
    args = parse_args(['--database-file', 'db.sql', 'file', 'list'])
    assert args.pop('database_file') == 'db.sql'

    args = parse_args(['-l', 'log-file', 'file', 'list'])
    assert args.pop('logging_file') == 'log-file'
    args = parse_args(['--logging-file', 'log-file', 'file', 'list'])
    assert args.pop('logging_file') == 'log-file'

    args = parse_args(['-k', 'key-file', 'file', 'list'])
    assert args.pop('crypto_key_file') == 'key-file'
    args = parse_args(['--crypto-key-file', 'key-file', 'file', 'list'])
    assert args.pop('crypto_key_file') == 'key-file'

    args = parse_args(['-r', '/home/foo', 'file', 'list'])
    assert args.pop('relative_path') == '/home/foo'
    args = parse_args(['--relative-path', '/home/foo', 'file', 'list'])
    assert args.pop('relative_path') == '/home/foo'

    args = parse_args(['-w', '/tmp/back', 'file', 'list'])
    assert args.pop('work_directory') == '/tmp/back'
    args = parse_args(['--work-directory', '/tmp/back', 'file', 'list'])
    assert args.pop('work_directory') == '/tmp/back'

    args = parse_args(['-c', 'oci.conf', 'file', 'list'])
    assert args.pop('oci_config_file') == 'oci.conf'
    args = parse_args(['--oci-config-file', 'oci.conf', 'file', 'list'])
    assert args.pop('oci_config_file') == 'oci.conf'

    args = parse_args(['-cs', 'DEFAULT', 'file', 'list'])
    assert args.pop('oci_config_section') == 'DEFAULT'
    args = parse_args(['--oci-config-section', 'DEFAULT', 'file', 'list'])
    assert args.pop('oci_config_section') == 'DEFAULT'

    args = parse_args(['-n', 'foo-namespace', 'file', 'list'])
    assert args.pop('oci_namespace') == 'foo-namespace'
    args = parse_args(['--oci-namespace', 'foo-namespace', 'file', 'list'])
    assert args.pop('oci_namespace') == 'foo-namespace'

    args = parse_args(['-b', 'bar-bucket', 'file', 'list'])
    assert args.pop('oci_bucket') == 'bar-bucket'
    args = parse_args(['--oci-bucket', 'bar-bucket', 'file', 'list'])
    assert args.pop('oci_bucket') == 'bar-bucket'

    blank_args = parse_args(['file', 'list'])
    assert blank_args.pop('module') == 'file'
    assert blank_args.pop('command') == 'list'
    blank_args.pop('settings_file') == DEFAULT_SETTINGS_FILE
    for _key, value in blank_args.items():
        assert value == None

def test_file():
    args = parse_args(['file', 'list'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'list'

    args = parse_args(['file', 'duplicates'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'duplicates'

    args = parse_args(['file', 'cleanup'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'cleanup'
    assert args['dry_run'] == False

    args = parse_args(['file', 'cleanup', '--dry-run'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'cleanup'
    assert args['dry_run'] == True

    args = parse_args(['file', 'backup', 'test-file'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'
    assert args.pop('overwrite') == False
    assert args.pop('check_uploaded_md5') == False

    args = parse_args(['file', 'backup', 'test-file', '-o'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'
    assert args.pop('overwrite') == True

    args = parse_args(['file', 'backup', 'test-file', '--overwrite'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'
    assert args.pop('overwrite') == True

    args = parse_args(['file', 'backup', 'test-file', '-m'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'
    assert args.pop('check_uploaded_md5') == True

    args = parse_args(['file', 'backup', 'test-file', '--check-uploaded-md5'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'
    assert args.pop('check_uploaded_md5') == True

    with pytest.raises(CLIException) as error:
        parse_args(['file', 'restore', 'foo'])
    assert str(error.value) == "argument local_file_id: invalid int value: 'foo'"
    args = parse_args(['file', 'restore', '1234'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'restore'
    assert args.pop('local_file_id') == 1234
    assert args.pop('overwrite') == False
    assert args.pop('set_restore') == False

    args = parse_args(['file', 'restore', '1234', '-o'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'restore'
    assert args.pop('local_file_id') == 1234
    assert args.pop('overwrite') == True

    args = parse_args(['file', 'restore', '1234', '--overwrite'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'restore'
    assert args.pop('local_file_id') == 1234
    assert args.pop('overwrite') == True

    args = parse_args(['file', 'restore', '1234', '-sr'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'restore'
    assert args.pop('local_file_id') == 1234
    assert args.pop('set_restore') == True

    args = parse_args(['file', 'restore', '1234', '--set-restore'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'restore'
    assert args.pop('local_file_id') == 1234
    assert args.pop('set_restore') == True

    args = parse_args(['file', 'md5', 'test-file'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'md5'
    assert args.pop('local_file') == 'test-file'

    args = parse_args(['file', 'encrypt', 'in-file', 'out-file'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'encrypt'
    assert args.pop('local_input_file') == 'in-file'
    assert args.pop('local_output_file') == 'out-file'

    with pytest.raises(CLIException) as error:
        parse_args(['file', 'decrypt', 'in-file', 'out-file', 'foo'])
    assert str(error.value) == "argument offset: invalid int value: 'foo'"
    args = parse_args(['file', 'decrypt', 'in-file', 'out-file', '14'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'decrypt'
    assert args.pop('local_input_file') == 'in-file'
    assert args.pop('local_output_file') == 'out-file'
    assert args.pop('offset') == 14

def test_backup():
    args = parse_args(['backup', 'list'])
    assert args.pop('module') == 'backup'
    assert args.pop('command') == 'list'

    args = parse_args(['backup', 'cleanup'])
    assert args.pop('module') == 'backup'
    assert args.pop('command') == 'cleanup'
    assert args.pop('dry_run') == False

    args = parse_args(['backup', 'cleanup', '--dry-run'])
    assert args.pop('module') == 'backup'
    assert args.pop('command') == 'cleanup'
    assert args.pop('dry_run') == True

def test_directory():
    args = parse_args(['directory', 'backup', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('overwrite') == False
    assert args.pop('check_uploaded_md5') == False
    assert args.pop('skip_files') == None
    assert args.pop('cache_file') == None

    args = parse_args(['directory', 'backup', 'test-dir', '-o'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('overwrite') == True

    args = parse_args(['directory', 'backup', 'test-dir', '--overwrite'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('overwrite') == True

    args = parse_args(['directory', 'backup', 'test-dir', '-m'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('check_uploaded_md5') == True

    args = parse_args(['directory', 'backup', 'test-dir', '--check-uploaded-md5'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('check_uploaded_md5') == True

    args = parse_args(['directory', 'backup', 'test-dir', '-f', 'test-one', 'test-two'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('skip_files') == ['test-one', 'test-two']

    args = parse_args(['directory', 'backup', 'test-dir', '--skip-files', 'test-one', 'test-two'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('skip_files') == ['test-one', 'test-two']

    args = parse_args(['directory', 'backup', 'test-dir', '-cf', 'cachey'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('cache_file') == 'cachey'

    args = parse_args(['directory', 'backup', 'test-dir', '--cache-file', 'cachey'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_path') == 'test-dir'
    assert args.pop('cache_file') == 'cachey'