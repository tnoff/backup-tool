#!/usr/bin/env python

import code
import oci

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import md5

class ObjectStorageClient():
    def __init__(self, config_file, config_section):
        config = oci.config.from_file(config_file, config_section)
        self.object_storage_client = oci.object_storage.ObjectStorageClient(config)

    def object_list(self, namespace_name, bucket_name):
        all_objects = []
        next_page = None
        fields = "name,md5,size,timeCreated"
        while True:
            try:
                response = self.object_storage_client.list_objects(namespace_name,
                                                                   bucket_name,
                                                                   start=next_page,
                                                                   limit=1,
                                                                   fields=fields)
            except oci.exceptions.ServiceError as error:
                raise ObjectStorageException("Error list objects:%s" % str(error))
            if response.status != 200:
                raise ObjectStorageException("Error list objects:%s" % response.data)
            all_objects += [oci.util.to_dict(object) for object in response.data.objects]
            next_page = response.data.next_start_with
            if next_page == None:
                return all_objects

    def object_put(self, namespace_name, bucket_name, object_name,
                   file_name, md5_sum=None):
        if md5_sum is None:
            md5_sum = md5(file_name)
        with open(file_name, 'rb') as reader:
            response = self.object_storage_client.put_object(namespace_name,
                                                             bucket_name,
                                                             object_name,
                                                             reader,
                                                             content_md5=md5_sum)
            if response.status != 200:
                raise ObjectStorageException("Error uploading object:%s" % response.data)
        return None

    def object_delete(self, namespace_name, bucket_name, object_name):
        response = self.object_storage_client.delete_object(namespace_name,
                                                            bucket_name,
                                                            object_name)
        if response.status != 200:
            raise ObjectStorageException("Error deleting object:%s" % response.data)
        return None
