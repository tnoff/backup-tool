import unittest

import mock

from backup_tool import utils
from backup_tool.client import BackupClient
from backup_tool.oci_client import ObjectStorageClient

from tests.utils import MockOS, MockOS404, to_dict_mock

class TestClient(unittest.TestCase):
    def test_client_basic_upload(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with utils.temp_file(suffix='.sql') as temp_db:
                            client = BackupClient(temp_db, '1234567890123456', 'fake config', 'fake section',
                                                  'fake namespace', 'fake bucket')
                            with utils.temp_file() as temp_file:
                                with open(temp_file, 'w') as writer:
                                    writer.write(utils.random_string(length=2048))
                                client.file_backup(temp_file)
                            # Should be one backup file with one local file
                            file_list = client.file_list()
                            self.assertEqual(len(file_list), 1)

                            backup_list = client.backup_list()
                            self.assertEqual(len(backup_list), 1)

    def test_client_upload_same_file(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with utils.temp_file(suffix='.sql') as temp_db:
                            client = BackupClient(temp_db, '1234567890123456', 'fake config', 'fake section',
                                                  'fake namespace', 'fake bucket')

                            randomish_string = utils.random_string(length=2048)

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
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with utils.temp_file(suffix='.sql') as temp_db:
                            client = BackupClient(temp_db, '1234567890123456', 'fake config', 'fake section',
                                                  'fake namespace', 'fake bucket')

                            with utils.temp_file() as temp_file:
                                with open(temp_file, 'w') as writer:
                                    writer.write(utils.random_string(length=20))
                                client.file_backup(temp_file)

                                with open(temp_file, 'w') as writer:
                                    writer.write(utils.random_string(length=32))
                                client.file_backup(temp_file)

                            # Should be one backup file with one local file
                            file_list = client.file_list()
                            self.assertEqual(len(file_list), 1)

                            backup_list = client.backup_list()
                            self.assertEqual(len(backup_list), 2)

    def test_client_no_overwrite(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with utils.temp_file(suffix='.sql') as temp_db:
                            client = BackupClient(temp_db, '1234567890123456', 'fake config', 'fake section',
                                                  'fake namespace', 'fake bucket')

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
