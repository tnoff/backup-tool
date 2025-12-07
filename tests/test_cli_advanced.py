"""
Advanced CLI tests to improve coverage
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from mock import patch

from backup_tool import utils
from backup_tool.cli.client import ClientCLI
from backup_tool.exception import CLIException


class MockOSClient:
    def __init__(self, *args, **kwargs):
        pass

    def object_put(self, *args, **kwargs):
        return True

    def object_delete(self, *args, **kwargs):
        return True


def test_crypto_key_file_loading():
    """Test that crypto key is loaded from file"""
    with TemporaryDirectory() as tmp_dir:
        # Create a crypto key file
        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456\n')

        # Create a config with crypto_key_file
        with patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient()):
            client_cli = ClientCLI(**{
                'module': 'file',
                'command': 'list',
                'general': {
                    'crypto_key_file': str(crypto_key_file),
                },
                'oci': {},
            })
            # Should have loaded the key
            assert client_cli.client.crypto_key == '1234567890123456'


def test_crypto_key_file_not_found():
    """Test that missing crypto key file raises error"""
    with pytest.raises(CLIException) as error:
        with patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient()):
            ClientCLI(**{
                'module': 'file',
                'command': 'list',
                'general': {
                    'crypto_key_file': '/nonexistent/key',
                },
                'oci': {},
            })
    assert 'does not exist' in str(error.value)


def test_directory_backup_basic(mocker):
    """Test basic directory backup functionality"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        # Create test directory with files
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        # Create some test files
        (test_dir / 'file1.txt').write_text('content1')
        (test_dir / 'file2.txt').write_text('content2')

        # Create crypto key
        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        client_cli = ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': None,
            'cache_file': None,
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        })

        client_cli.run_command()

        # Verify files were backed up
        backup_list = client_cli.client.backup_list()
        assert len(backup_list) == 2


def test_directory_backup_with_skip_files(mocker):
    """Test directory backup with skip_files pattern"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        # Create test files
        (test_dir / 'file1.txt').write_text('content1')
        (test_dir / 'secret.txt').write_text('secret')
        (test_dir / 'file2.txt').write_text('content2')

        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        client_cli = ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': ['.*secret.*'],
            'cache_file': None,
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        })

        client_cli.run_command()

        # Only 2 files should be backed up (secret.txt skipped)
        backup_list = client_cli.client.backup_list()
        assert len(backup_list) == 2


def test_directory_backup_with_cache_file(mocker):
    """Test directory backup with cache file"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        (test_dir / 'file1.txt').write_text('content1')

        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        cache_file = Path(tmp_dir) / 'cache.json'

        with ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': None,
            'cache_file': str(cache_file),
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        }) as client_cli:
            client_cli.run_command()

        # Cache file should exist after context exit
        assert cache_file.exists()

        # Verify cache structure
        cache_data = json.loads(cache_file.read_text())
        assert 'backup' in cache_data
        assert 'pending_upload' in cache_data['backup']
        assert 'processed' in cache_data['backup']


def test_directory_backup_with_symlinks(mocker):
    """Test that symlinks are skipped during directory backup"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        # Create a regular file
        (test_dir / 'file1.txt').write_text('content1')

        # Create a symlink
        target = test_dir / 'target.txt'
        target.write_text('target content')
        symlink = test_dir / 'link.txt'
        symlink.symlink_to(target)

        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        client_cli = ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': None,
            'cache_file': None,
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        })

        client_cli.run_command()

        # Should backup 2 regular files, symlink should be skipped
        backup_list = client_cli.client.backup_list()
        assert len(backup_list) == 2


def test_cache_file_path_expansion(mocker):
    """Test that cache_file is converted to Path object"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        (test_dir / 'file1.txt').write_text('content1')

        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        cache_file_str = str(Path(tmp_dir) / 'cache.json')

        with ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': None,
            'cache_file': cache_file_str,
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        }) as client_cli:
            client_cli.run_command()
            # Verify cache_file is a Path object (not string) after running command
            assert isinstance(client_cli.cache_file, Path)

        # Verify cache file was created
        assert Path(cache_file_str).exists()


def test_cli_exit_with_cache_file(mocker):
    """Test that cache file is written on exit"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / 'test_backup'
        test_dir.mkdir()

        (test_dir / 'file1.txt').write_text('content1')

        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'work'
        work_dir.mkdir()

        cache_file = Path(tmp_dir) / 'cache.json'

        with ClientCLI(**{
            'module': 'directory',
            'command': 'backup',
            'dir_paths': [str(test_dir)],
            'overwrite': False,
            'skip_files': None,
            'cache_file': str(cache_file),
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {
                'namespace': 'test-ns',
                'bucket': 'test-bucket',
            },
        }) as client_cli:
            client_cli.run_command()

        # Cache file should be written on context exit
        assert cache_file.exists()
        cache_data = json.loads(cache_file.read_text())
        assert len(cache_data['backup']['processed']) > 0


def test_work_directory_from_config(mocker):
    """Test that work_directory is read from config"""
    mocker.patch('backup_tool.client.OCIObjectStorageClient', return_value=MockOSClient())

    with TemporaryDirectory() as tmp_dir:
        crypto_key_file = Path(tmp_dir) / 'crypto-key'
        crypto_key_file.write_text('1234567890123456')

        work_dir = Path(tmp_dir) / 'custom_work'

        client_cli = ClientCLI(**{
            'module': 'file',
            'command': 'list',
            'general': {
                'crypto_key_file': str(crypto_key_file),
                'work_directory': str(work_dir),
            },
            'oci': {},
        })

        # Verify work directory was created
        assert work_dir.exists()
        assert client_cli.client.work_directory == work_dir
