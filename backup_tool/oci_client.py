import os
import shutil

import oci
from oci.retry import DEFAULT_RETRY_STRATEGY
from oci.object_storage import UploadManager
from oci.exceptions import ServiceError

from oci.object_storage.models import RestoreObjectsDetails

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import temp_file, md5, setup_logger

class ObjectStorageClient():
    def __init__(self, config_file, config_section, logger=None):
        config = oci.config.from_file(config_file, config_section)
        self.object_storage_client = oci.object_storage.ObjectStorageClient(config,
                                                                            retry_strategy=DEFAULT_RETRY_STRATEGY)
        self.upload_manager = UploadManager(self.object_storage_client)
        if logger is None:
            self.logger = setup_logger("oci_client", 10)
        else:
            self.logger = logger

    def object_list(self, namespace_name, bucket_name, page_limit=30):
        all_objects = []
        next_page = None
        fields = "name,md5,size,timeCreated"
        self.logger.info("Retrieving object list from namespace %s and bucket %s",
                         namespace_name, bucket_name)
        while True:
            try:
                response = self.object_storage_client.list_objects(namespace_name,
                                                                   bucket_name,
                                                                   start=next_page,
                                                                   limit=page_limit,
                                                                   fields=fields)
            except oci.exceptions.ServiceError as error:
                raise ObjectStorageException("Error list objects:%s" % str(error))
            if response.status != 200:
                raise ObjectStorageException("Error list objects:%s" % response.data)
            all_objects += [oci.util.to_dict(obj) for obj in response.data.objects]
            next_page = response.data.next_start_with
            self.logger.debug("Retrieved list of up to %s objects, next page %s", page_limit, next_page)
            if next_page is None:
                return all_objects


    def object_put(self, namespace_name, bucket_name, object_name,
                   file_name, md5_sum=None, force_multipart_upload=False, multipart_chunk_size=128 * (2 ** 20)):
        self.logger.info("Starting upload of file %s to namespace %s bucket %s and object name %s",
                         file_name, namespace_name, bucket_name, object_name)
        response = self.upload_manager.upload_file(namespace_name, bucket_name, object_name, file_name, content_md5=md5_sum)
        if response.status != 200:
            raise ObjectStorageException("Error uploading object:%s" % response.data)
        self.logger.info("File %s uploaded to object storage with object name %s", file_name, object_name)
        return True

    def object_get(self, namespace_name, bucket_name, object_name, file_name, chunk_size=128 * (2 ** 20), set_restore=False):
        self.logger.info("Downloading object %s from namespace %s and bucket %s to file %s",
                         object_name, namespace_name, bucket_name, file_name)
        with open(file_name, 'wb') as writer:
            try:
                response = self.object_storage_client.get_object(namespace_name,
                                                                 bucket_name,
                                                                 object_name)
            except ServiceError as error:
                self.logger.error("Service Error when attempting to download object:%s" % str(error))
                if set_restore and "'code': 'NotRestored'" in str(error):
                    self.logger.debug("Object %s in bucket %s and namepsace %s is archived, will mark for restore",
                                      object_name, bucket_name, namespace_name)
                    restore_details = RestoreObjectsDetails(object_name=object_name)
                    response = self.object_storage_client.restore_objects(namespace_name, bucket_name, restore_details)
                    if response.status != 202:
                        raise ObjectStorageException("Error restoring object:%s" % response.data)
                    self.logger.info("Set restore on object %s in bucket %s and namespace %s", object_name, bucket_name, namespace_name)
                return False

            if response.status != 200:
                raise ObjectStorageException("Error downloading object:%s" % response.data)
            self.logger.debug("Writing object %s to file %s using %s chunk size",
                              object_name, file_name, chunk_size)
            shutil.copyfileobj(response.data.raw, writer)
        return True

    def object_delete(self, namespace_name, bucket_name, object_name):
        self.logger.info("Deleting object %s from namespace %s and bucket %s",
                         object_name, namespace_name, bucket_name)
        response = self.object_storage_client.delete_object(namespace_name,
                                                            bucket_name,
                                                            object_name)
        if response.status != 204:
            raise ObjectStorageException("Error deleting object:%s" % response.status)
        return True
