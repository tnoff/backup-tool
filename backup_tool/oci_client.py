import os

import oci

from oci.object_storage.models import CreateMultipartUploadDetails, CommitMultipartUploadDetails, CommitMultipartUploadPartDetails

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import temp_file, md5, setup_logger

class ObjectStorageClient():
    def __init__(self, config_file, config_section, logger=None):
        config = oci.config.from_file(config_file, config_section)
        self.object_storage_client = oci.object_storage.ObjectStorageClient(config)
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

    def _multipart_upload(self, namespace_name, bucket_name, object_name, file_name, multipart_chunk_size):
        self.logger.debug("Starting multipart upload of file %s", file_name)

        # First create a multipart upload, save upload id
        multi_part_model_kwargs = {
            'object' : object_name,
        }
        multi_part_model = CreateMultipartUploadDetails(**multi_part_model_kwargs)
        response = self.object_storage_client.create_multipart_upload(namespace_name,
                                                                      bucket_name,
                                                                      multi_part_model)
        upload_id = response.data.upload_id
        self.logger.debug("Multipart upload id %s for upload of file %s", upload_id, file_name)

        # Split file into parts of size 128 MB or less
        # Upload each section as a part
        # TODO add pooling/threading for this

        upload_parts = []
        # Multipart uploads start at 1 for w/e reason
        current_part = 1
        self.logger.debug("Opening file %s and uploading %s size chunks", multipart_chunk_size, file_name)
        with open(file_name, 'rb') as reader:
            while True:
                self.logger.debug("Attempting to write chunk number %s of file %s", current_part, file_name)
                chunk = reader.read(multipart_chunk_size)
                if not chunk:
                    break

                # Write to temp file, and then generate md5
                with temp_file() as chunk_file:
                    self.logger.debug("Writing chunk data of file %s to temp file %s", file_name, chunk_file)
                    with open(chunk_file, 'wb') as writer:
                        writer.write(chunk)
                    chunk_md5 = md5(chunk_file)
                    self.logger.debug("Chunk file %s has md5 sum %s", chunk_file, chunk_md5)

                    # Now open chunk file and write part
                    with open(chunk_file, 'rb') as chunk_read:
                        # Upload chunk with proper info
                        self.logger.debug("Uploading chunk %s to object storage", chunk_file)
                        response = self.object_storage_client.upload_part(namespace_name,
                                                                          bucket_name,
                                                                          object_name,
                                                                          upload_id,
                                                                          current_part,
                                                                          chunk_read,
                                                                          content_md5=chunk_md5)
                    if response.status != 200:
                        raise ObjectStorageException("Error part upload:%s" % response.data)
                    # Save the partial commit info
                    part_details = CommitMultipartUploadPartDetails(part_num=current_part,
                                                                    etag=response.headers['ETag'])
                    upload_parts.append(part_details)
                    self.logger.debug("Chunk upload successful, part %s and etag %s", current_part, response.headers['ETag'])
                # Make sure to iterate current part
                current_part += 1

        self.logger.debug("All parts uploaded for file %s, commiting multi part upload", file_name)
        # Combine part uploads and commit
        commit_details = CommitMultipartUploadDetails(parts_to_commit=upload_parts)
        response = self.object_storage_client.commit_multipart_upload(namespace_name, bucket_name, object_name,
                                                                      upload_id, commit_details)
        if response.status != 200:
            raise ObjectStorageException("Error part multipart commit:%s" % response.data)
        return True

    def object_put(self, namespace_name, bucket_name, object_name,
                   file_name, md5_sum=None, force_multipart_upload=False, multipart_chunk_size=128 * (2 ** 20)):
        self.logger.info("Starting upload of file %s to namespace %s bucket %s and object name %s",
                         file_name, namespace_name, bucket_name, object_name)
        # Multipart upload caps out at 1000 parts, which in the current 128 MB chunks maxes out at 125 GB
        # If theres ever need to upload a file that big, deal with it then
        if os.path.getsize(file_name) > 134217728000:
            raise ObjectStorageException("File size too big for this client to upload")

        # Get size of file, if greater than 128 MB, use multipart uploads
        if (os.path.getsize(file_name) / (2 ** 20)) > 128 or force_multipart_upload:
            self._multipart_upload(namespace_name, bucket_name, object_name, file_name, multipart_chunk_size)
        else:
            if md5_sum is None:
                self.logger.debug("No object md5 sum for file %s given, generating one now", file_name)
                md5_sum = md5(file_name)
            self.logger.debug("File %s smaller than 128 MB, uploading all in one go", file_name)
            with open(file_name, 'rb') as reader:
                response = self.object_storage_client.put_object(namespace_name,
                                                                 bucket_name,
                                                                 object_name,
                                                                 reader,
                                                                 content_md5=md5_sum)
                if response.status != 200:
                    raise ObjectStorageException("Error uploading object:%s" % response.data)
        self.logger.info("File %s uploaded to object storage with object name %s", file_name, object_name)
        return True

    def object_get(self, namespace_name, bucket_name, object_name, file_name, chunk_size=128 * (2 ** 20)):
        self.logger.info("Downloading object %s from namespace %s and bucket %s to file %s",
                         object_name, namespace_name, bucket_name, file_name)
        with open(file_name, 'wb') as writer:
            response = self.object_storage_client.get_object(namespace_name,
                                                             bucket_name,
                                                             object_name)
            if response.status != 200:
                raise ObjectStorageException("Error downloading object:%s" % response.data)
            self.logger.debug("Writing object %s to file %s using %s chunk size",
                              object_name, file_name, chunk_size)
            for chunk in response.data.raw.stream(chunk_size, decode_content=True):
                writer.write(chunk)
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
