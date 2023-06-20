from copy import deepcopy
from tempfile import TemporaryDirectory

from mock import patch, call
import pytest

from backup_tool import utils
from backup_tool.cli.client import ClientCLI
from backup_tool.cli.client import DEFAULT_SETTINGS_FILE
from backup_tool.cli.client import parse_args, load_settings, generate_args
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

    args = parse_args(['file', 'backup', 'test-file'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'

    args = parse_args(['file', 'backup', 'test-file'])
    assert args.pop('module') == 'file'
    assert args.pop('command') == 'backup'
    assert args.pop('local_file') == 'test-file'

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
    args = parse_args(['directory', 'backup', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('overwrite') == False
    assert args.pop('skip_files') == None
    assert args.pop('cache_file') == None

    args = parse_args(['directory', 'backup', '-o', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('overwrite') == True

    args = parse_args(['directory', 'backup', '--overwrite', '--dir-paths', 'test-dir',])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('overwrite') == True

    args = parse_args(['directory', 'backup', '--dir-paths', 'test-dir',])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']

    args = parse_args(['directory', 'backup', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']

    args = parse_args(['directory', 'backup', '-f', 'test-one', 'test-two', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('skip_files') == ['test-one', 'test-two']

    args = parse_args(['directory', 'backup', '--skip-files', 'test-one', 'test-two', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('skip_files') == ['test-one', 'test-two']

    args = parse_args(['directory', 'backup', '-cf', 'cachey', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('cache_file') == 'cachey'

    args = parse_args(['directory', 'backup', '--cache-file', 'cachey', '--dir-paths', 'test-dir'])
    assert args.pop('module') == 'directory'
    assert args.pop('command') == 'backup'
    assert args.pop('dir_paths') == ['test-dir']
    assert args.pop('cache_file') == 'cachey'

def test_load_settings():
    result = load_settings(None)
    assert result == {}

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text(' ')
            result = load_settings(str(settings_file))
        assert result == {}

        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text('general:\n  logging_file: foo.log\n  database_file: db.sql')
            result = load_settings(str(settings_file))
        assert result['general']['logging_file'] == 'foo.log'
        assert result['general']['database_file'] == 'db.sql'

        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text('general:\n  crypto_key_file: /home/foo/key\n  relative_path: /home/foo')
            result = load_settings(str(settings_file))
        assert result['general']['crypto_key_file'] == '/home/foo/key'
        assert result['general']['relative_path'] == '/home/foo'

        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text('oci:\n  config_file: /home/oci/config\n  config_section: DEFAULT')
            result = load_settings(str(settings_file))
        assert result['oci']['config_file'] == '/home/oci/config'
        assert result['oci']['config_section'] == 'DEFAULT'

        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text('oci:\n  namespace: foo\n  bucket: bar')
            result = load_settings(str(settings_file))
        assert result['oci']['namespace'] == 'foo'
        assert result['oci']['bucket'] == 'bar'

def test_generate_args():
    result = generate_args(['file', 'list'])
    assert result['module'] == 'file'
    assert result['command'] == 'list'

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as settings_file:
            settings_file.write_text('general:\n  logging_file: foo.log')
            result = generate_args(['-s', str(settings_file), 'file', 'list'])
            assert result['general']['logging_file'] == 'foo.log'

@patch('builtins.print')
def test_cli_client(mocker):
    x = ClientCLI(**{
        'module': 'file',
        'command': 'list',
    })
    x.run_command()
    assert mocker.mock_calls == [call('[]')]