import unittest

import mock

from backup_tool import utils
from backup_tool.client import BackupClient
from backup_tool.oci_client import ObjectStorageClient

def from_file_config_mock(config_file, config_section):
    return 'mock config'

def to_dict_mock(object_data):
    return vars(object_data)


class MockObjectOne():
    def __init__(self):
        self.name = 'foo.csv'
        self.size = 1234
        self.md5 = "9i9RHkgTENq8BSSGzKmqxg=="
        self.timeCreated = "2019-07-21T23:22:54.663000+00:00"


class MockObjectTwo():
    def __init__(self):
        self.name = 'bar.csv'
        self.size = 4561
        self.md5 = "fnqonfqowenfAoGzKmqxg=="
        self.timeCreated = "2019-07-24T23:23:54.663000+00:00"


class MockObjectData():
    def __init__(self, objects, start):
        self.objects = objects
        self.next_start_with = start


class MockObjectResponse():
    def __init__(self, status_code, data=None, objects=None, start=None):
        self.status = status_code
        # For list objects
        if data:
            self.data = data
        else:
            self.data = MockObjectData(objects, start)


class MockOS():
    def __init__(self, _config):
        pass

    def list_objects(self, namespace_name, bucket_name, **kwargs):
        if kwargs.get('start') is None:
            return MockObjectResponse(200, objects=[MockObjectOne()], start="bar.ods")
        else:
            return MockObjectResponse(200, objects=[MockObjectTwo()], start=None)

    def put_object(self, namespace_name, bucket_name, object_name, put_object_body, **kwargs):
        return MockObjectResponse(200)

    def delete_object(self, namespace_name, bucket_name, object_name, **kwargs):
        return MockObjectResponse(200)


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
