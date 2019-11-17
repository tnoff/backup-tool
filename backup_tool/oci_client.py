#!/usr/bin/env python

import os

import oci

from oci.object_storage.models import CreateMultipartUploadDetails, CommitMultipartUploadDetails, CommitMultipartUploadPartDetails

from backup_tool.exception import ObjectStorageException
from backup_tool.utils import temp_file, md5

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
        # Multipart upload caps out at 1000 parts, which in the current 128 MB chunks maxes out at 125 GB
        # If theres ever need to upload a file that big, deal with it then
        if ( os.path.getsize(file_name) > 134217728000 ):
            raise ObjectStorageException("File size too big for this client to upload")

        # Get size of file, if greater than 128 MB, use multipart uploads
        if ( os.path.getsize(file_name) / ( 2 ** 20 )) > 128:
            # Start upload
            multi_part_model_kwargs = {
                'object' : object_name,
            }
            multi_part_model = CreateMultipartUploadDetails(**multi_part_model_kwargs)
            response = self.object_storage_client.create_multipart_upload(namespace_name,
                                                                          bucket_name,
                                                                          multi_part_model)
            upload_id = response.data.upload_id

            # Split file into parts of size 128 MB or less
            # Upload each section as a part

            upload_parts = []
            current_part = 0
            temp_files = []
            with open(file_name, 'rb') as reader:
                while True:
                    chunk = reader.read(128 * ( 2 ** 20))
                    if not chunk:
                        break
                    with temp_file(delete=False) as chunk_file:
                        with open(chunk_file, 'wb') as writer:
                            writer.write(chunk)
                        chunk_md5 = md5(chunk_file)

                        temp_files.append({
                            'file_name' : chunk_file,
                            'md5' : chunk_md5
                        })
                # TODO add pooling/threading for this
                for (current_part, chunk_file) in enumerate(temp_files):
                    with open(chunk_file['file_name'], 'rb') as chunk_read:
                        # Upload parts must be between 1 and 1000, so just add 1
                        response = self.object_storage_client.upload_part(namespace_name,
                                                                          bucket_name,
                                                                          object_name,
                                                                          upload_id,
                                                                          current_part + 1,
                                                                          chunk_read,
                                                                          content_md5=chunk_file['md5'])
                    part_details = CommitMultipartUploadPartDetails(part_num=current_part + 1,
                                                                    etag=response.headers['Etag'])
                    upload_parts.append(part_details)

            commit_details = CommitMultipartUploadDetails(parts_to_commit=upload_parts)
            self.object_storage_client.commit_multipart_upload(namespace_name, bucket_name, object_name,
                                                               upload_id, commit_details) 

            for chunk_file in temp_files:
                os.remove(chunk_file['file_name'])

        else:
            with open(file_name, 'rb') as reader:
                response = self.object_storage_client.put_object(namespace_name,
                                                                 bucket_name,
                                                                 object_name,
                                                                 reader,
                                                                 content_md5=md5_sum)
                if response.status != 200:
                    raise ObjectStorageException("Error uploading object:%s" % response.data)
        return True, 1

    def object_get(self, namespace_name, bucket_name, object_name, file_name, chunk_size=1024):
        with open(file_name, 'wb') as writer:
            response = self.object_storage_client.get_object(namespace_name,
                                                             bucket_name,
                                                             object_name)
            if response.status != 200:
                raise ObjectStorageException("Error downloading object:%s" % response.data)
            for chunk in response.data.raw.stream(chunk_size, decode_content=True):
                writer.write(chunk)

    def object_delete(self, namespace_name, bucket_name, object_name):
        response = self.object_storage_client.delete_object(namespace_name,
                                                            bucket_name,
                                                            object_name)
        if response.status != 200:
            raise ObjectStorageException("Error deleting object:%s" % response.data)
        return None
