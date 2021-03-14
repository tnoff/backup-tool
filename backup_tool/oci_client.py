import shutil

from oci.config import from_file
from oci.retry import DEFAULT_RETRY_STRATEGY
from oci.exceptions import ServiceError
from oci.object_storage import ObjectStorageClient, UploadManager
from oci.util import to_dict

from oci.object_storage.models import RestoreObjectsDetails

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import setup_logger

class OCIObjectStorageClient():
    '''
    Object Storage Client
    '''
    def __init__(self, config_file, config_section, logger=None):
        '''
        Create ObjectStorageClient for OCI

        config_file     :   OCI Configuration File
        config_section  :   OCI Config File Section
        logger          :   Logger, if not given one will be created
        '''
        config = from_file(config_file, config_section)
        self.object_storage_client = ObjectStorageClient(config, retry_strategy=DEFAULT_RETRY_STRATEGY)
        self.upload_manager = UploadManager(self.object_storage_client)
        if logger is None:
            self.logger = setup_logger("oci_client", 10)
        else:
            self.logger = logger

    def object_list(self, namespace_name, bucket_name, page_limit=1024):
        '''
        Return list of object storage objects

        namespace_name  :   Object Storage Namespace
        bucket_name     :   Bucket Name
        page_limit      :   Page Limit for Object Storage Calls
        '''
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
            except ServiceError as error:
                raise ObjectStorageException from error
            if response.status != 200:
                raise ObjectStorageException(f'Error list objects: {str(error)}')
            all_objects += [to_dict(obj) for obj in response.data.objects]
            next_page = response.data.next_start_with
            self.logger.debug(f'Retrieved list of up to {page_limit} objects, next page {next_page}')
            if next_page is None:
                return all_objects

    def object_put(self, namespace_name, bucket_name, object_name, file_name, md5_sum=None):
        '''
        Upload object to object storage

        namespace_name  :   Object Storage Namespace
        bucket_name     :   Bucket name
        object_name     :   Name of uploaded object
        file_name       :   Name of local file to upload
        md5_sum         :   Md5 sum of local file
        '''
        self.logger.info(f'Starting upload of file "{file_name}" to namespace "{namespace_name}" '
                         f'bucket "{bucket_name}" and object name "{object_name}"')
        response = self.upload_manager.upload_file(namespace_name, bucket_name, object_name, file_name, content_md5=md5_sum)
        if response.status != 200:
            raise ObjectStorageException(f'Error uploading object: {str(response.data)}')
        self.logger.info(f'File "{file_name}" uploaded to object storage with object name "{object_name}"')
        return True

    def object_get(self, namespace_name, bucket_name, object_name, file_name, set_restore=False):
        '''
        Download object from object storage

        namespace_name  :   Object Storage Namespace
        bucket_name     :   Bucket name
        object_name     :   Name of object to download
        file_name       :   Name of local file where object will be downloaded
        set_restore     :   If object is archived, run "set_restore"
        '''
        self.logger.info(f'Downloading object "{object_name}" from namespace "{namespace_name}" and bucket "{bucket_name}" to file "{file_name}"')
        with open(file_name, 'wb') as writer:
            try:
                response = self.object_storage_client.get_object(namespace_name,
                                                                 bucket_name,
                                                                 object_name)
            except ServiceError as error:
                self.logger.exception(f'Service Error when attempting to download object: {str(error)}')
                if set_restore and "'code': 'NotRestored'" in str(error):
                    self.logger.debug(f'Object "{object_name}" in bucket "{bucket_name}" and namepsace '
                                      f'"{namespace_name}" is archived, will mark for restore')
                    restore_details = RestoreObjectsDetails(object_name=object_name)
                    response = self.object_storage_client.restore_objects(namespace_name, bucket_name, restore_details)
                    if response.status != 202:
                        raise ObjectStorageException from error
                    self.logger.info(f'Set restore on object "{object_name}" in bucket "{bucket_name}" and namespace "{namespace_name}"')
                return False

            if response.status != 200:
                raise ObjectStorageException(f'Error downloading object: {str(response.data)}')
            self.logger.debug(f'Writing object "{object_name}" to file "{file_name}"')
            shutil.copyfileobj(response.data.raw, writer)
        return True

    def object_delete(self, namespace_name, bucket_name, object_name):
        '''
        Delete object in object storage

        namespace_name  :   Object Storage Namespace
        bucket_name     :   Bucket name
        object_name     :   Name of object to delete
        '''
        self.logger.info(f'Deleting object "{object_name}" from namespace "{namespace_name}" and bucket "{bucket_name}"')
        response = self.object_storage_client.delete_object(namespace_name,
                                                            bucket_name,
                                                            object_name)
        if response.status != 204:
            raise ObjectStorageException(f'Error deleting object: {str(response.status)}')
        return True
