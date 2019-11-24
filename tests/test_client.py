import os
import unittest

import mock

from backup_tool import utils
from backup_tool.client import BackupClient
from backup_tool.oci_client import ObjectStorageClient

# Needs to be 16 chars long
FAKE_CRYPTO_KEY = '1234567890123456'
FAKE_CONFIG = 'faker_config'
FAKE_SECTION = 'default'
FAKE_NAMESPACE = 'citadel'
FAKE_BUCKET = 'dragons'

class MockOSClient():
    def __init__(self, *args, **kwargs):
        pass

    def object_put(self, *args, **kwargs):
        return True

class TestClient(unittest.TestCase):
    def test_client_basic_upload(self):
        '''
            Upload a single file, amke sure there is one file listed, and one backup listed
        '''
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                # Open file and write
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=124))
                    client.file_backup(temp_file)
                # Should be one backup file with one local file
                file_list = client.file_list()
                self.assertEqual(len(file_list), 1)
                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

    def test_client_two_files_same_md5(self):
        '''
            Upload two files with same content, make sure two files listed, but one backup
        '''
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                randomish_string = utils.random_string()
                # Write same file and upload twice
                with utils.temp_file() as temp_file1:
                    with open(temp_file1, 'w') as writer:
                        writer.write(randomish_string)
                    client.file_backup(temp_file1)

                    with utils.temp_file() as temp_file2:
                        with open(temp_file2, 'w') as writer:
                            writer.write(randomish_string)
                        client.file_backup(temp_file2)

                # Should be one backup file with one local file
                file_list = client.file_list()
                self.assertEqual(len(file_list), 2)

                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

    def test_client_overwrite_file(self):
        '''
            Upload a file, then overwrite that file with new data and upload
            Make sure only one local file copy, but two uploaded files
        '''
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=20))
                    client.file_backup(temp_file)

                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=32))
                    client.file_backup(temp_file, overwrite=True)

                # Should be one backup file with one local file
                file_list = client.file_list()
                self.assertEqual(len(file_list), 1)

                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 2)

    def test_client_no_overwrite_file(self):
        '''
            Upload a file, then overwrite that file with new data and upload
            With overwrite turned off, should only be one backup copy
        '''
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=20))
                    client.file_backup(temp_file)

                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=32))
                    client.file_backup(temp_file, overwrite=False)

                # Should be one backup file with one local file
                file_list = client.file_list()
                self.assertEqual(len(file_list), 1)

                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

    # TODO test file restore
    # TODO test file skip
