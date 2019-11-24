import unittest

import mock

from backup_tool import utils
from backup_tool.exception import ObjectStorageException
from backup_tool.oci_client import ObjectStorageClient

def from_file_config_mock(config_file, config_section):
    return 'mock config'

def to_dict_mock(object_data):
    print("mocking object")
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

class MockDataStream():
    def __init__(self, objects):
        class Raw():
            def __init__(self, objects):
                self.objects = objects
            def stream(self, *args, **kwargs):
                return self.objects
        self.raw = Raw(objects)

class MockCreateMultipartData():
    def __init__(self, upload_id):
        self.upload_id = upload_id

class MockObjectResponse():
    def __init__(self, status_code, data=None, objects=None, start=None):
        self.status = status_code
        # For list objects
        if data:
            self.data = data
        else:
            self.data = MockObjectData(objects, start)


class MockOS404():
    def __init__(self, _config):
        pass

    def list_objects(self, namespace_name, bucket_name, **kwargs):
        return MockObjectResponse(404, data="Invalid response")

class MockPartHeaders():
    def __init__(self, etag):
        self.status = 200
        self.headers = {
            'ETag' : etag,
        }

class MockOS():
    def __init__(self, _config):
        pass

    def list_objects(self, namespace_name, bucket_name, **kwargs):
        if kwargs.get('start') is None:
            return MockObjectResponse(200, objects=[MockObjectOne()], start="bar.ods")
        else:
            return MockObjectResponse(200, objects=[MockObjectTwo()], start=None)

    def create_multipart_upload(self, namespace_name, bucket_name, multipart_details):
        return MockObjectResponse(200, data=MockCreateMultipartData(upload_id=1234))

    def get_object(self, namspeace_name, bucket_name, object_name, **kwargs):
        return MockObjectResponse(200, data=MockDataStream([bytearray('foo', 'utf8')]))

    def put_object(self, namespace_name, bucket_name, object_name, put_object_body, **kwargs):
        return MockObjectResponse(200)

    def delete_object(self, namespace_name, bucket_name, object_name, **kwargs):
        return MockObjectResponse(200)

    def upload_part(self, namespace_name, bucket_name, object_name, upload_id,
                    current_part, file_chunk, **kwargs):
        return MockPartHeaders('abcdefgt')

    def commit_multipart_upload(self, namepsace_name, bucket_name, object_name, upload_id, commit_details):
        return MockPartHeaders('dofanoaefnoenf')

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
