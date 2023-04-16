import shutil

from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
from oci.config import from_file
from oci.retry import DEFAULT_RETRY_STRATEGY
from oci.exceptions import ServiceError
from oci.object_storage import ObjectStorageClient, UploadManager
from oci.util import to_dict

from oci.object_storage.models import RestoreObjectsDetails
from oci.pagination import list_call_get_all_results

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import setup_logger

class OCIObjectStorageClient():
    '''
    Object Storage Client
    '''
    def __init__(self, config_file, config_section, logger=None, instance_principal=False):
        '''
        Create ObjectStorageClient for OCI

        config_file         :   OCI Configuration File
        config_section      :   OCI Config File Section
        logger              :   Logger, if not given one will be created
        instance_principal  :   Use instance principal for auth
        '''
        if not instance_principal:
            config = from_file(config_file, config_section)
            self.object_storage_client = ObjectStorageClient(config, retry_strategy=DEFAULT_RETRY_STRATEGY)
        else:
            signer = InstancePrincipalsSecurityTokenSigner()
            iself.object_storage_client = ObjectStorageClient(config={}, signer=signer, retry_strategy=DEFAULT_RETRY_STRATEGY)
        self.upload_manager = UploadManager(self.object_storage_client)
        if logger is None:
            self.logger = setup_logger("oci_client", 10)
        else:
            self.logger = logger

    def object_list(self, namespace_name, bucket_name):
        '''
        Return list of object storage objects

        namespace_name  :   Object Storage Namespace
        bucket_name     :   Bucket Name
        '''
        self.logger.info("Retrieving object list from namespace %s and bucket %s",
                         namespace_name, bucket_name)
        all_objects_response = list_call_get_all_results(self.object_storage_client.list_objects,
                                                         namespace_name, bucket_name, fields='name,md5,size,timeCreated')
        return [to_dict(obj) for obj in all_objects_response.data.objects]


    def object_put(self, namespace_name, bucket_name, object_name, file_name, md5_sum=None, resume_upload=False):
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
        upload_resumed = False
        if resume_upload:
            self.logger.debug(f'Checking if object name "{object_name}" is in list of pending uploads')
            multipart_uploads = list_call_get_all_results(self.object_storage_client.list_multipart_uploads,
                                                          namespace_name, bucket_name)
            for multipart_upload in multipart_uploads.data:
                # Assume namespace and bucket are the same
                if multipart_upload.object == object_name:
                    self.logger.debug(f'Resuming file upload {multipart_upload.upload_id} for object "{object_name}"')
                    response = self.upload_manager.resume_upload_file(namespace_name, bucket_name, object_name, file_name, multipart_upload.upload_id)
                    upload_resumed = True
                    break
        if not upload_resumed:
            response = self.upload_manager.upload_file(namespace_name, bucket_name, object_name, file_name, content_md5=md5_sum)
        if response.status != 200:
            raise ObjectStorageException(f'Error uploading object, Reponse code {str(response.status)}')
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
                get_response = self.object_storage_client.get_object(namespace_name,
                                                                     bucket_name,
                                                                     object_name)
            except ServiceError as error:
                self.logger.exception(f'Service Error when attempting to download object: {str(error)}')
                if set_restore and "'code': 'NotRestored'" in str(error):
                    self.logger.debug(f'Object "{object_name}" in bucket "{bucket_name}" and namepsace '
                                      f'"{namespace_name}" is archived, will mark for restore')
                    restore_details = RestoreObjectsDetails(object_name=object_name)
                    restore_response = self.object_storage_client.restore_objects(namespace_name, bucket_name, restore_details)
                    if restore_response.status != 202:
                        raise ObjectStorageException('Error restoring object, ' # pylint:disable=raise-missing-from
                                                     f'Response code {str(restore_response.status)}')
                    self.logger.info(f'Set restore on object "{object_name}" in bucket "{bucket_name}" and namespace "{namespace_name}"')
                return False

            if get_response.status != 200:
                raise ObjectStorageException(f'Error downloading object, Response code {str(get_response.status)}')
            self.logger.debug(f'Writing object "{object_name}" to file "{file_name}"')
            shutil.copyfileobj(get_response.data.raw, writer)
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
            raise ObjectStorageException(f'Error deleting object, Reponse code {str(response.status)}')
        return True
