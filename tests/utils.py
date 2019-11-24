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

    def list_objects(self, *args, **kwargs):
        if kwargs.get('start') is None:
            return MockObjectResponse(200, objects=[MockObjectOne()], start="bar.ods")
        else:
            return MockObjectResponse(200, objects=[MockObjectTwo()], start=None)

    def create_multipart_upload(self, *args, **kwargs):
        return MockObjectResponse(200, data=MockCreateMultipartData(upload_id=1234))

    def get_object(self, *args, **kwargs):
        return MockObjectResponse(200, data=MockDataStream([bytearray('foo', 'utf8')]))

    def put_object(self, *args, **kwargs):
        return MockObjectResponse(200)

    def delete_object(self, *args, **kwargs):
        return MockObjectResponse(200)

    def upload_part(self, *args, **kwargs):
        return MockPartHeaders('abcdefgt')

    def commit_multipart_upload(self, *args, **kwargs):
        return MockPartHeaders('dofanoaefnoenf')
