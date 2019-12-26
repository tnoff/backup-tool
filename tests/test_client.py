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

    def object_delete(self, *args, **kwargs):
        return True

class TestClient(unittest.TestCase):
    def test_basic_upload(self):
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
                # Files should have diff md5s
                self.assertNotEqual(file_list[0]['local_md5_checksum'], backup_list[0]['uploaded_md5_checksum'])

    def test_file_backup_same_md5s(self):
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
                self.assertEqual(file_list[0]['local_md5_checksum'], file_list[1]['local_md5_checksum'])

                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

    def test_file_backup_overwrite(self):
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

                # Should be diff md5s
                self.assertNotEqual(backup_list[0]['uploaded_md5_checksum'], backup_list[1]['uploaded_md5_checksum'])

    def test_file_backup_no_overwrite(self):
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

    def test_file_restore(self):
        '''
            Upload a file, remove the local copy, attempt to download again
        '''

        random_data = utils.random_string()

        class MockOSGet():
            def __init__(self, *args, **kwargs):
                pass
            def object_put(self, *args, **kwargs):
                return True
            def object_get(self, _ns, _bn, _on, file_name, **kwargs):
                with open(file_name, 'w') as writer:
                    writer.write(random_data)
                return True

        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSGet
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(random_data)
                    client.file_backup(temp_file)

                local_file = client.file_list()[0]

                # Make sure file not there currently
                self.assertFalse(os.path.isfile(local_file['local_file_path']))

                # Attempt to download file again, will fail if md5 doesnt match
                with utils.temp_file(name=local_file['local_file_path']) as temp_file:
                    client.file_restore(local_file['id'])

    def test_file_encrypt(self):
        class MockOS():
            def __init__(self, *args, **kwargs):
                pass
        with utils.temp_file(suffix='.sql') as temp_db:
            with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOS
                with utils.temp_file() as temp_file_input:
                    # Write some dummy data to file
                    with open(temp_file_input, 'w') as writer:
                        writer.write('1234567890123456')
                    with utils.temp_file() as temp_file_output:
                        client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                              FAKE_NAMESPACE, FAKE_BUCKET)

                        offset = client.file_encrypt(temp_file_input, temp_file_output)
                        self.assertEqual(offset, 0)

                        with open(temp_file_output, 'r') as reader:
                            read_data = reader.read()
                        self.assertEqual(read_data, 'dXzNDNxckOrb7uz2ON0AAA==')

    def test_file_decrypt(self):
        with utils.temp_file(suffix='.sql') as temp_db:
            with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOSClient
                with utils.temp_file() as temp_file_input:
                    # Write some dummy data to file
                    with open(temp_file_input, 'w') as writer:
                        writer.write('dXzNDNxckOrb7uz2ON0AAA==')
                    with utils.temp_file() as temp_file_output:
                        client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                              FAKE_NAMESPACE, FAKE_BUCKET)

                        client.file_decrypt(temp_file_input, temp_file_output, 0)

                        with open(temp_file_output, 'r') as reader:
                            read_data = reader.read()
                        self.assertEqual(read_data, '1234567890123456')

    def test_file_cleanup(self):
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                # First upload temp file
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=20))
                    client.file_backup(temp_file)

                # Now run file cleanup since temp file is deleted
                client.file_cleanup()

                # Test file list is empty
                file_list = client.file_list()
                self.assertEqual(len(file_list), 0)

                # Test backup file still exists
                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

    def test_backup_cleanup(self):
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                # First upload temp file
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write(utils.random_string(length=20))
                    client.file_backup(temp_file)

                # Now run file cleanup since temp file is deleted
                client.file_cleanup()

                # Make sure backup list not empty
                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

                # Now run backup cleanup
                client.backup_cleanup()

                # Make sure backup list is empty
                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 0)


    def test_file_duplicates(self):
        with mock.patch("backup_tool.oci_client.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSClient
            with utils.temp_file(suffix='.sql') as temp_db:
                client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                      FAKE_NAMESPACE, FAKE_BUCKET)
                # First upload temp file
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write('abc')
                    client.file_backup(temp_file)

                # Upload temp file of same data
                with utils.temp_file() as temp_file:
                    with open(temp_file, 'w') as writer:
                        writer.write('abc')
                    client.file_backup(temp_file)


                # Make sure there are two files, but one backup
                file_list = client.file_list()
                self.assertEqual(len(file_list), 2)

                backup_list = client.backup_list()
                self.assertEqual(len(backup_list), 1)

                # Now test duplicates
                duplicates = client.file_duplicates()
                # Make sure there is one key with a list of 2 items
                keys = list(duplicates.keys())
                self.assertEqual(len(keys), 1)

                self.assertEqual(len(duplicates[keys[0]]), 2)

    # TODO test file skip
