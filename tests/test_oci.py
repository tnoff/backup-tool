import os
import unittest
import pytest

import oci
from oci.exceptions import ServiceError
from oci.object_storage import ObjectStorageClient

from backup_tool import utils
from backup_tool.exception import ObjectStorageException
from backup_tool.oci_client import OCIObjectStorageClient

FAKE_CONFIG = 'faker_config'
FAKE_SECTION = 'default'
FAKE_NAMESPACE = 'citadel'
FAKE_BUCKET = 'dragons'

def to_dict_mock(object_data):
    return vars(object_data)

class MockObject():
    def __init__(self, name, size, md5):
        self.name = name
        self.size = size
        self.md5 = md5
        self.timeCreated = "2019-07-21T23:22:54.663000+00:00"

class MockResponse():
    def __init__(self, status, data):
        self.status = status
        self.data = data

class MockList():
    def __init__(self, objects):
        self.objects = objects
        self.next_start_with = None

#
# Object List Tests
#

def test_object_list(mocker):
    '''
    Test basic object list
    '''
    fake_name = utils.random_string()
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def list_objects(self, *args, **kwargs):
            return MockResponse(200, MockList([MockObject(fake_name, 123, '0123456')]))
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    # Make sure to pass page limit of 1
    objects = client.object_list(FAKE_NAMESPACE, FAKE_BUCKET, page_limit=1)
    assert len(objects) == 1
    assert objects[0]['name'] == fake_name

def test_object_list_invalid_status(mocker):
    '''
    Test object list with non-200 status code fails
    '''
    fake_name = utils.random_string()
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def list_objects(self, *args, **kwargs):
            return MockResponse(400, '')
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    with pytest.raises(ObjectStorageException) as error:
        client.object_list(FAKE_NAMESPACE, FAKE_BUCKET, page_limit=1)
    assert str(error.value) == 'Error list objects, Reponse code 400'

def test_object_list_raise_exception(mocker):
    '''
    Test object list with non-200 status code fails
    '''
    fake_name = utils.random_string()
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def list_objects(self, *args, **kwargs):
            raise ServiceError(500, 500, {}, f'Unable to retrieve list due to white walkers')
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    with pytest.raises(ObjectStorageException) as error:
        client.object_list(FAKE_NAMESPACE, FAKE_BUCKET, page_limit=1)


#
# Object Get Tests
#

def test_object_get(mocker):
    test_data = '01234'
    with utils.temp_file() as input_file:
        with open(input_file, 'w') as writer:
            writer.write(test_data)
        with open(input_file, 'rb') as reader:
            class MockRawRequest():
                def __init__(self):
                    self.raw = reader
            class MockOCI():
                def __init__(self, *args, **kwargs):
                    pass

                def get_object(self, *args, **kwargs):
                    return MockResponse(200, MockRawRequest())

            mocker.patch('backup_tool.oci_client.from_file',
                         return_value='')
            mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                         return_value=MockOCI)
            mocker.patch('backup_tool.oci_client.to_dict',
                         side_effect=to_dict_mock)
            client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
            # Make sure to pass page limit of 1
            with utils.temp_file() as temp_file:
                objects = client.object_get(FAKE_NAMESPACE, FAKE_BUCKET,
                                            'some-object-name', temp_file)
                md5 = utils.md5(temp_file)
                assert md5 == 'QQDE1E2pF3JH5EpfwVRneA=='

def test_object_get_invalid_status(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def get_object(self, *args, **kwargs):
            return MockResponse(400, None)

    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    # Make sure to pass page limit of 1
    with utils.temp_file() as temp_file:
        with pytest.raises(ObjectStorageException) as error:
            client.object_get(FAKE_NAMESPACE, FAKE_BUCKET,
                              'some-object-name', temp_file)
    assert str(error.value) == 'Error downloading object, Response code 400'

def test_object_get_restore(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def get_object(self, *args, **kwargs):
            raise ServiceError(400, 400, {}, "'code': 'NotRestored'")

        def restore_objects(self, *args, **kwargs):
            return MockResponse(202, None)

    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    # Make sure to pass page limit of 1
    with utils.temp_file() as temp_file:
        client.object_get(FAKE_NAMESPACE, FAKE_BUCKET,
                          'some-object-name', temp_file, set_restore=True)

def test_object_get_restore_invalid_status(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def get_object(self, *args, **kwargs):
            raise ServiceError(400, 400, {}, "'code': 'NotRestored'")

        def restore_objects(self, *args, **kwargs):
            return MockResponse(400, None)

    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    # Make sure to pass page limit of 1
    with utils.temp_file() as temp_file:
        with pytest.raises(ObjectStorageException) as error:
            client.object_get(FAKE_NAMESPACE, FAKE_BUCKET,
                              'some-object-name', temp_file, set_restore=True)
    assert str(error.value) == 'Error restoring object, Response code 400'

#
# Object Delete Tests
#

def test_object_delete(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def delete_object(self, *args, **kwargs):
            return MockResponse(204, None)
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    client.object_delete(FAKE_NAMESPACE, FAKE_BUCKET, 'some-object-name')

def test_object_delete_invalid_status(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass

        def delete_object(self, *args, **kwargs):
            return MockResponse(400, f'Cannot delete object, raven never delivered message')
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    with pytest.raises(ObjectStorageException) as error:
        client.object_delete(FAKE_NAMESPACE, FAKE_BUCKET, 'some-object-name')
    assert str(error.value) == 'Error deleting object, Reponse code 400'

#
# Object Put Tests
#

def test_object_put(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass
    class MockUploadManager():
        def __init__(self, *args, **kwargs):
            pass
        def upload_file(self, *args, **kwargs):
            return MockResponse(200, None)
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.UploadManager',
                 return_value=MockUploadManager)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    fake_data = utils.random_string()
    with utils.temp_file() as temp_file:
        with open(temp_file, 'w+') as writer:
            writer.write(fake_data)
            client.object_put(FAKE_NAMESPACE, FAKE_BUCKET, 'some-object-name', temp_file)

def test_object_put_invalid_status(mocker):
    class MockOCI():
        def __init__(self, *args, **kwargs):
            pass
    class MockUploadManager():
        def __init__(self, *args, **kwargs):
            pass
        def upload_file(self, *args, **kwargs):
            return MockResponse(400, f'This aint Valyrian steel')
    mocker.patch('backup_tool.oci_client.from_file',
                 return_value='')
    mocker.patch('backup_tool.oci_client.ObjectStorageClient',
                 return_value=MockOCI)
    mocker.patch('backup_tool.oci_client.UploadManager',
                 return_value=MockUploadManager)
    mocker.patch('backup_tool.oci_client.to_dict',
                 side_effect=to_dict_mock)
    client = OCIObjectStorageClient(FAKE_CONFIG, FAKE_SECTION)
    fake_data = utils.random_string()
    with utils.temp_file() as temp_file:
        with open(temp_file, 'w+') as writer:
            writer.write(fake_data)
        with pytest.raises(ObjectStorageException) as error:
            client.object_put(FAKE_NAMESPACE, FAKE_BUCKET, 'some-object-name', temp_file)
        assert str(error.value) == 'Error uploading object, Reponse code 400'
