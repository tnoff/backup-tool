import os
import unittest

import mock

from backup_tool import utils
from backup_tool.exception import ObjectStorageException
from backup_tool.oci_client import ObjectStorageClient

FAKE_CONFIG = '''
'''
CONFIG_SECTION = 'DEFAULT'
FAKE_NAMESPACE = 'citadel'
FAKE_BUCKET = 'dragons'
FAKE_OBJECT = 'The Dance of the Dragons, A True Telling'

def to_dict_mock(object_data):
    return vars(object_data)

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

class TestOCI(unittest.TestCase):
    def setUp(self):
        # Setup oci config file
        with utils.temp_file(delete=False) as temp_config:
            with open(temp_config, 'w') as writer:
                writer.write(FAKE_CONFIG)
            # Save for teardown
            self.temp_config = temp_config

    def cleanup(self):
        os.remove(self.temp_config)

    def test_object_list(self):
        '''
            Test object list w/ pagination
        '''
        # Generate some fake data for objects
        fake_name_one = utils.random_string()
        fake_name_two = utils.random_string()
        fake_md5_one = utils.random_string()
        fake_md5_two = utils.random_string()

        # Mock out object data
        class MockObjectOne():
            def __init__(self):
                self.name = fake_name_one
                self.size = 1234
                self.md5 = fake_md5_one
                self.timeCreated = "2019-07-21T23:22:54.663000+00:00"
        class MockObjectTwo():
            def __init__(self):
                self.name = fake_name_two
                self.size = 4561
                self.md5 = fake_md5_two
                self.timeCreated = "2019-07-24T23:23:54.663000+00:00"

        # Mock client
        class MockOSListObjects():
            def __init__(self, *args, **kwargs):
                pass

            # Mock client pagination
            # One first response, return first object with a next page key
            # One second response, just return second item with no next page key
            def list_objects(self, *args, **kwargs):
                if kwargs.get('start') is None:
                    return MockObjectResponse(200, objects=[MockObjectOne()], start=fake_name_two)
                else:
                    return MockObjectResponse(200, objects=[MockObjectTwo()], start=None)

        with mock.patch("oci.util.to_dict") as mock_to_dict:
            mock_to_dict.side_effect = to_dict_mock
            with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
                mock_os.side_effect = MockOSListObjects
                client = ObjectStorageClient(self.temp_config, CONFIG_SECTION)
                # Make sure to pass page limit of 1
                objects = client.object_list(FAKE_NAMESPACE, FAKE_BUCKET, page_limit=1)
                # Check two items in list, make sure in proper order
                self.assertEqual(len(objects), 2)
                self.assertEqual(objects[0]['md5'], fake_md5_one)
                self.assertEqual(objects[1]['md5'], fake_md5_two)

    def test_object_put(self):
        '''
            Test basic object put
        '''
        class MockOSPutObject():
            def __init__(self, *args, **kwargs):
                pass

            def put_object(self, namespace_name, bucket_name, object_name, file_name, **kwargs):
                # Open file, then check later if file has been opened
                return MockObjectResponse(200)

        with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSPutObject
            client = ObjectStorageClient(self.temp_config, CONFIG_SECTION)
            with utils.temp_file() as temp_object:
                with open(temp_object, 'w') as w:
                    w.write(utils.random_string())
                client.object_put(FAKE_NAMESPACE, FAKE_BUCKET, FAKE_OBJECT, temp_object)

    def test_object_multipart_upload(self):
        '''
            Test multi part upload
        '''

        upload_id = 1234
        fake_etag = utils.random_string()

        class MockCreateMultipartData():
            def __init__(self):
                self.upload_id = upload_id

        class MockPartHeaders():
            def __init__(self, etag):
                self.status = 200
                self.headers = {
                    'ETag' : etag,
                }

        class MockOSMultipart():
            def __init__(self, *args, **kwargs):
                pass

            def create_multipart_upload(self, *args, **kwargs):
                return MockObjectResponse(200, data=MockCreateMultipartData())

            def upload_part(self, *args, **kwargs):
                return MockPartHeaders(fake_etag)

            def commit_multipart_upload(self, *args, **kwargs):
                return MockPartHeaders(fake_etag)

        with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSMultipart
            client = ObjectStorageClient(self.temp_config, CONFIG_SECTION)
            with utils.temp_file() as temp_object:
                with open(temp_object, 'w') as w:
                    w.write(utils.random_string())
                client.object_put(FAKE_NAMESPACE, FAKE_BUCKET, FAKE_OBJECT, temp_object,
                                  force_multipart_upload=True, multipart_chunk_size=1)
    def test_object_delete(self):
        '''
            Test basic object delete
        '''
        class MockOSDelete():
            def __init__(self, *args, **kwargs):
                pass

            def delete_object(self, *args, **kwargs):
                return MockObjectResponse(200)

        with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSDelete
            client = ObjectStorageClient(self.temp_config, CONFIG_SECTION)
            client.object_delete(FAKE_NAMESPACE, FAKE_BUCKET, FAKE_OBJECT)

    def test_object_get(self):
        '''
            Test object download
        '''

        random_string = utils.random_string()

        class MockDataStream():
            def __init__(self):
                class Raw():
                    def __init__(self):
                        self.objects = [bytearray(random_string, 'utf8')]
                    def stream(self, *args, **kwargs):
                        return self.objects
                self.raw = Raw()

        class MockOSGet():
            def __init__(self, _config):
                pass

            def get_object(self, *args, **kwargs):
                return MockObjectResponse(200, data=MockDataStream())

        with mock.patch("oci.object_storage.ObjectStorageClient") as mock_os:
            mock_os.side_effect = MockOSGet
            client = ObjectStorageClient(self.temp_config, CONFIG_SECTION)
            with utils.temp_file() as temp_object:
                client.object_get(FAKE_NAMESPACE, FAKE_BUCKET, FAKE_OBJECT, temp_object)

                with open(temp_object, 'rb') as reader:
                    data = reader.read()
                    # String within b'string-foo'
                    self.assertEqual(str(data)[2:-1], random_string)
