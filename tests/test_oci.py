import unittest

import mock

from backup_tool import utils
from backup_tool.exception import ObjectStorageException
from backup_tool.oci_client import ObjectStorageClient

from tests.utils import MockOS, MockOS404, to_dict_mock

class TestOCI(unittest.TestCase):
    def test_object_list_404(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOS404
                client = ObjectStorageClient('fake config', 'fake section')
                with self.assertRaises(ObjectStorageException) as error:
                    client.object_list("fake namespace", "fake bucket")
                self.assertEqual("Error list objects:Invalid response", str(error.exception))


    def test_object_list(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    objects = client.object_list("fake namespace", "fake bucket")
                    self.assertEqual(len(objects), 2)
                    self.assertEqual(objects[0]['md5'], "9i9RHkgTENq8BSSGzKmqxg==")
                    self.assertEqual(objects[1]['md5'], "fnqonfqowenfAoGzKmqxg==")

    def test_object_put(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with open(temp_object, 'w') as w:
                            w.write(utils.random_string(length=1024))
                        client.object_put('fake namespace', 'fake bucket', 'fake object', temp_object)

    def test_object_multipart_upload(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.util.to_dict") as mock_to_dict:
                mock_to_dict.side_effect = to_dict_mock
                with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                    mock_os.side_effect = MockOS
                    client = ObjectStorageClient('fake config', 'fake section')
                    with utils.temp_file() as temp_object:
                        with open(temp_object, 'w') as w:
                            w.write(utils.random_string(length=1024))
                        client.object_put('fake namespace', 'fake bucket', 'fake object', temp_object,
                                          force_multipart_upload=True, multipart_chunk_size=50)

    def test_object_delete(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOS
                client = ObjectStorageClient('fake config', 'fake section')
                client.object_delete('fake namespace', 'fake bucket', 'fake object')

    def test_object_get(self):
        with mock.patch("oci.config.from_file") as mock_config:
            mock_config.return_value = "mock config"
            with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOS
                client = ObjectStorageClient('fake config', 'fake section')
                with utils.temp_file() as temp_object:
                    client.object_get('fake namespace', 'fake section', 'fake object', temp_object)

                    with open(temp_object, 'rb') as reader:
                        data = reader.read()
                        self.assertEqual(data, b'foo')
