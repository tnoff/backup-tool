from multiprocessing import Process, cpu_count
import os
import re
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backup_tool import crypto
from backup_tool.oci_client import OCIObjectStorageClient
from backup_tool.database import BASE, BackupEntry, BackupEntryLocalFile
from backup_tool import utils

class BackupClient():
    '''
    Backup Client
    '''
    def __init__(self, database_file, crypto_key, oci_config_file, oci_config_section, oci_namespace, oci_bucket,
                 logging_file=None, relative_path=None, threads=cpu_count() * 2):
        '''
        Backup Client

        database_file   :   Path for sqlite database
        crypto_key      :   Crytography Passphrase
        oci_config_file :   Path of OCI Config File
        oci_config_section  : Path of OCI Config Section
        oci_namespace   :   OCI Object Storage Namespace
        oci_bucket      :   OCI Object Storage Bucket
        logging_file    :   Path for logging file
        relative_path   :   Where files should be placed relative to machine
        threads         :   Number of threads to use during multiple uploads

        Relative path explanation:
        If relative path given as "/home/user"

        If uploading file of path "/home/user/Documents/essay.txt", the relative path will be removed before adding the path to the database.
        This means the path stored in the database will be "Documents/essay.txt"

        Then when restoring files, the relative path will be added to the prefix of the files in the database.
        So if the database has "Documents/essay.txt", the full path of the restored file will be "/home/user/Documents/essay.txt"

        The basic idea here is to make moving files between different types of machines easier
        '''

        self.logger = utils.setup_logger('backup_client', 10, logging_file=logging_file)

        if database_file is None:
            engine = create_engine('sqlite:///', encoding='utf-8')
            self.logger.debug('Initializing database with no file')
        else:
            engine = create_engine(f'sqlite:///{database_file}', encoding='utf-8')
            self.logger.debug(f'Initializing database with file: "{database_file}"')

        BASE.metadata.create_all(engine)
        BASE.metadata.bind = engine
        self.db_session = sessionmaker(bind=engine)()

        self.crypto_key = crypto_key
        self.relative_path = relative_path

        self.oci_namespace = oci_namespace
        self.oci_bucket = oci_bucket
        self.os_client = OCIObjectStorageClient(oci_config_file, oci_config_section, logger=self.logger)
        self.cpu_threads = threads

    def _generate_uuid(self):
        '''
        Generate a uuid that is not already in use
        '''
        # Make sure object path does not exist already
        while True:
            object_path = str(uuid.uuid4())

            existing_path = self.db_session.query(BackupEntry).\
                    filter(BackupEntry.uploaded_file_path == object_path).first()
            if not existing_path:
                return object_path
            self.logger.warning(f'UUID "{object_path}" already in use, generating another')

    def file_restore(self, local_file_id, overwrite=False, set_restore=False):
        '''
        Restore file from object storage

        local_file_id   :   ID of local file database entry to restore locally
        overwrite       :   Overwrite local file if md5 does not match
        set_restore     :   If object is archived, attempt to restore
        '''
        self.logger.info(f'Restoring local file: {local_file_id}')

        local_file = self.db_session.query(BackupEntryLocalFile).get(local_file_id)
        if not local_file:
            self.logger.error(f'Unable to find local file: {local_file_id}')
            return False

        if not local_file.backup_entry_id:
            self.logger.error(f'No backup entry for local file: {local_file_id}')
            return False

        backup_entry = self.db_session.query(BackupEntry).get(local_file.backup_entry_id)

        if not backup_entry:
            self.logger.error(f'Expecting backup entry {local_file.backup_entry_id} does not exist')

        local_file_path = local_file.local_file_path
        if self.relative_path:
            local_file_path = os.path.join(self.relative_path, local_file_path)

        if os.path.isfile(local_file_path):
            self.logger.debug(f'Checking local file "{local_file_path}" md5')
            local_file_md5 = utils.md5(local_file_path)
            self.logger.debug(f'Local file "{local_file_path}" has md5 sum {local_file_md5}')
            if local_file.local_md5_checksum == local_file_md5:
                if not overwrite:
                    self.logger.info(f'Local file "{local_file_path}" has expected md5 {local_file_md5}')
                    return True

        # Write file to temp dir
        with utils.temp_file() as encrypted_file:
            self.logger.info(f'Downloading object {backup_entry.uploaded_file_path} to temp file "{encrypted_file}"')
            self.os_client.object_get(self.oci_namespace, self.oci_bucket,
                                      backup_entry.uploaded_file_path, encrypted_file, set_restore=set_restore)
            self.logger.info(f'Downloaded of object {backup_entry.uploaded_file_path} complete, written to temp file "{encrypted_file}"')

            # Check md5 matches expected
            self.logger.debug(f'Checking md5 sum of temp file "{encrypted_file}"')
            downloaded_md5 = utils.md5(encrypted_file)
            self.logger.debug(f'Downloaded encrypted file "{encrypted_file}" has md5 sum {downloaded_md5}')
            if backup_entry.uploaded_md5_checksum != downloaded_md5:
                self.logger.error(f'Downloaded file "{encrypted_file}" has unexpected md5 {downloaded_md5}, '
                                  f'expected {backup_entry.uploaded_md5_checksum}')
                return True
            self.logger.debug(f'Decrypting temp file "{encrypted_file}" to file "{local_file_path}"')
            dir_name = os.path.dirname(local_file_path)
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            local_file_md5 = crypto.decrypt_file(encrypted_file, local_file_path, self.crypto_key,
                                                 backup_entry.uploaded_encryption_offset)


        self.logger.debug(f'Local file "{local_file_path}" has md5 sum {local_file_md5}')
        if local_file_md5 != local_file.local_md5_checksum:
            self.logger.error(f'MD5 {local_file_md5} of decrypted file "{local_file_path}" does not match expected {local_file.local_md5_checksum}')
            return False
        return True


    def file_md5(self, local_file): #pylint: disable=no-self-use
        '''
        Get md5sum of local file

        local_file      :       Full path of local file
        '''
        return utils.md5(local_file)

    def file_encrypt(self, local_input_file, local_output_file):
        '''
        Encrypt local file, but no dot upload

        local_input_file    :   Full path of local input file
        local_ouput_file    :   Full path of local ouptut file
        '''
        offset, original_md5, encrypted_md5 = crypto.encrypt_file(local_input_file, local_output_file, self.crypto_key)
        self.logger.info(f'Encrypted local file "{local_input_file}" with md5 sum {original_md5} '
                         f' to output file "{local_output_file} with offset {offset} and md5 sum {encrypted_md5}')
        return {'offset': offset, 'encrypted_md5': encrypted_md5, 'original_md5': original_md5}

    def file_decrypt(self, local_input_file, local_output_file, offset):
        '''
        Decrypt local file

        local_input_file    :   Full path of local input file
        local_ouput_file    :   Full path of local ouptut file
        offset              :   Offset number to use in decryption
        '''
        md5 = crypto.decrypt_file(local_input_file, local_output_file, self.crypto_key, offset)
        self.logger.info(f'Derypted local file "{local_input_file}" to output file "{local_output_file}" with md5 {md5}')
        return md5

    def file_backup(self, local_file, overwrite=False, check_uploaded_md5=False):
        '''
        Backup file to object storage

        local_file          :       Full path of local file
        overwrite           :       Upload new file is md5 is changed
        check_uploaded_md5  :       Ensure any existing backup file matches expected encryption
        '''
        self._file_backup(local_file, overwrite=overwrite, check_uploaded_md5=check_uploaded_md5)

    def _file_backup_file_exists(self, local_backup_file, local_file, local_file_md5, overwrite, check_uploaded_md5):
        '''
        Local backup of file exists
        '''
        # Keep boolean value to make sure we should upload new file
        upload_file = True

        self.logger.debug(f'Found existing local file: {local_backup_file.id}')
        if local_file_md5 == local_backup_file.local_md5_checksum:
            self.logger.debug(f'Existing local file "{local_file}" has expected md5 {local_file_md5}')
            # Only upload if no backup file exists
            # If requested, check that backup file matches encryption
            if local_backup_file.backup_entry_id is not None and check_uploaded_md5 is False:
                upload_file = False
        else:
            self.logger.debug(f'Existing local file "{local_file}" has unexpected md5 sum {local_file_md5}')
            if overwrite is True:
                local_backup_file.local_md5_checksum = local_file_md5
                # Current file has no backup, so set this to null for now
                local_backup_file.backup_entry_id = None
                self.db_session.commit()
                self.logger.debug(f'Updated local file {local_backup_file.id} to checksum {local_file_md5}')
            else:
                self.logger.warning(f'Overwrite set to false, not uploading new version of local file "{local_file}"')
                upload_file = False
        return upload_file

    def _file_backup_upload(self, crypto_file, local_crypto_file_md5, offset, local_backup_file):
        # Check if md5 file already exists
        backup_entry = self.db_session.query(BackupEntry).\
                filter(BackupEntry.uploaded_md5_checksum == local_crypto_file_md5).first()

        if backup_entry:
            # If file exists, just upload local files data
            self.logger.debug(f'Found existing upload with matching md5 found {backup_entry.id} for '
                              f'file with md5 "{local_crypto_file_md5}"')
            local_backup_file.backup_entry_id = backup_entry.id
            self.db_session.commit()
            self.logger.info(f'Updated local file {local_backup_file.id} with backup entry {backup_entry.id}')
            return True

        # Else upload new file
        self.logger.info(f'No encrypted upload matching file with md5 {local_crypto_file_md5}, uploading copy')
        object_path = self._generate_uuid()

        self.logger.debug(f'Uploading encrypted file "{crypto_file}" to object path {object_path}')
        self.os_client.object_put(self.oci_namespace, self.oci_bucket, object_path, crypto_file,
                                  md5_sum=local_crypto_file_md5)

        backup_args = {
            'uploaded_file_path' : object_path,
            'uploaded_md5_checksum' : local_crypto_file_md5,
            'uploaded_encryption_offset' : offset,
        }

        backup_entry = BackupEntry(**backup_args)
        self.db_session.add(backup_entry)
        self.db_session.commit()
        self.logger.info(f'Uploaded encrypted file "{crypto_file}" as backup entry {backup_entry.id}')

        local_backup_file.backup_entry_id = backup_entry.id
        self.db_session.commit()
        self.logger.info(f'Updated local backup {local_backup_file.id} to match backup entry {backup_entry.id}')
        return True

    def _file_backup(self, local_file, overwrite=False, check_uploaded_md5=False):
        '''
        Backup file to object storage

        local_file          :       Full path of local file
        overwrite           :       Upload new file is md5 is changed
        check_uploaded_md5  :       Ensure any existing backup file matches expected encryption
        '''
        # Use local file as the full path of the file
        # Use local file path as relative path for the database
        local_file = os.path.abspath(local_file)
        if self.relative_path:
            local_file_path = os.path.relpath(local_file, self.relative_path)
        else:
            local_file_path = local_file
        self.logger.info(f'Backing up local file: "{local_file}"')
        if local_file_path != local_file:
            self.logger.debug(f'Using relative path for database "{local_file_path}"')

        with utils.temp_file() as crypto_file:
            self.logger.debug(f'Creating encrypted file "{crypto_file}" from file "{local_file}"')
            offset, local_file_md5, local_crypto_file_md5 = crypto.encrypt_file(local_file, crypto_file, self.crypto_key)
            self.logger.debug(f'Created encrypted file "{crypto_file}" with md5 "{local_crypto_file_md5}" '
                              f' from original file "{local_file}" with md5 "{local_file_md5}"')

            local_backup_file = self.db_session.query(BackupEntryLocalFile).\
                    filter(BackupEntryLocalFile.local_file_path == local_file_path).first()
            if local_backup_file:
                upload_file = self._file_backup_file_exists(local_backup_file, local_file,
                                                            local_file_md5, overwrite, check_uploaded_md5)
            else:
                upload_file = True
                self.logger.debug(f'No existing local file found for path: "{local_file}"')
                backup_file_args = {
                    'local_file_path': local_file_path,
                    'local_md5_checksum' : local_file_md5,
                }

                local_backup_file = BackupEntryLocalFile(**backup_file_args)
                self.db_session.add(local_backup_file)
                self.db_session.commit()
                self.logger.info(f'Created database entry {local_backup_file.id} for local file "{local_file}"')

            if upload_file:
                return self._file_backup_upload(crypto_file, local_crypto_file_md5, offset, local_backup_file)
            return True

    def file_duplicates(self):
        '''
        Find backup files with multiple local file definitions
        '''
        # Get dict of
        # { backup_file_id : [<local file>, <local file>]
        backup_file_duplicates = {}
        for local_file in self.db_session.query(BackupEntryLocalFile).all():
            local_file_dict = local_file.as_dict()
            backup_file_id = local_file_dict.pop('backup_entry_id')
            backup_file_duplicates.setdefault(backup_file_id, [])
            backup_file_duplicates[backup_file_id].append(local_file_dict)

        # Remove entries that don't have multiple entries
        single_backups = []
        for backup_id, file_list in backup_file_duplicates.items():
            if len(file_list) < 2:
                single_backups.append(backup_id)
        for backup in single_backups:
            backup_file_duplicates.pop(backup)
        return backup_file_duplicates

    def __directory_backup(self, file_list, overwrite, check_uploaded_md5):
        for file_name in file_list:
            self._file_backup(file_name, overwrite=overwrite, check_uploaded_md5=check_uploaded_md5)

    def directory_backup(self, dir_path, overwrite=False, check_uploaded_md5=False, skip_files=None): #pylint:disable=too-many-locals
        '''
            Backup all files in directory

            local_file          :       Full path of local file
            overwrite           :       Upload new file is md5 is changed
            check_uploaded_md5  :       Ensure any existing backup file matches expected encryption
            skip_files          :       List of regexes to ignore for backup
        '''
        directory_path = os.path.abspath(dir_path)

        # Make sure skip files is a string type
        if skip_files is None:
            skip_files = []
        elif isinstance(skip_files, str):
            skip_files = [skip_files]

        # Add an empty list for each thread
        file_lists = []
        for _thread_num in range(self.cpu_threads):
            file_lists.append([])

        self.logger.info(f'Generating file list from directory "{directory_path}"')
        for count, (dir_name, _, file_list) in enumerate(os.walk(directory_path)):
            # Check if dir matches skip files
            skip_dir = False
            for skip_check in skip_files:
                if re.match(skip_check, dir_name):
                    self.logger.warning(f'Ignoring dir "{dir_name}" since matches skip check "{skip_check}"')
                    skip_dir = True
                    break
            if skip_dir:
                continue
            for file_name in file_list:
                full_path = os.path.join(dir_name, file_name)
                # Skip if matches any continue
                skip = False
                for skip_check in skip_files:
                    if re.match(skip_check, full_path):
                        self.logger.warning(f'Ignoring file "{full_path}" since matches skip check "{skip_check}"')
                        skip = True
                        break
                if skip:
                    continue
                self.logger.debug(f'Adding file to backup queue "{full_path}"')
                file_lists[count % self.cpu_threads].append(full_path)


        threads = []
        for thread_num in range(self.cpu_threads):
            self.logger.info(f'Starting thread number {thread_num}')
            process = Process(target=self.__directory_backup,
                              args=(file_lists[thread_num], overwrite, check_uploaded_md5))
            process.start()
            threads.append(process)

        for process in threads:
            self.logger.debug(f'Waiting for thread "{process.name}"')
            process.join()

    def file_list(self):
        '''
        List all local file database entries
        '''
        local_files = []
        for local_file in self.db_session.query(BackupEntryLocalFile).all():
            local_files.append(local_file.as_dict())
        return local_files

    def file_cleanup(self, dry_run=False):
        '''
        Delete local files in database that are no longer present on file system
        dry_run     :       Return list of files, but do not execute deletes
        '''

        files_cleaned = []

        for local_file in self.db_session.query(BackupEntryLocalFile).all():
            local_file_path = local_file.local_file_path
            if self.relative_path:
                local_file_path = os.path.join(self.relative_path, local_file_path)
            if not os.path.isfile(local_file_path):
                self.logger.info(f'Local file {local_file.id} path "{local_file_path}" no longer present, removing from db')
                if not dry_run:
                    self.db_session.query(BackupEntryLocalFile).filter_by(id=local_file.id).delete()
                files_cleaned.append(local_file.id)
            else:
                self.logger.debug(f'Local file {local_file.id} path "{local_file_path}" exists, skipping')
        self.db_session.commit()
        return files_cleaned


    def backup_list(self):
        '''
        List all external backup database entries
        '''
        backup_files = []
        for backup_entry in self.db_session.query(BackupEntry).all():
            backup_files.append(backup_entry.as_dict())
        return backup_files

    def backup_cleanup(self, dry_run=False):
        '''
        Find backup entries that do not have a local file entry, and delete these backups
        dry_run     :   Return list of files, but do not delete
        '''
        backup_entry_ids = [item[0] for item in self.db_session.query(BackupEntry.id)]
        local_file_backups = [item[0] for item in self.db_session.query(BackupEntryLocalFile.backup_entry_id).distinct()]

        extra_backup_entries = list(set(backup_entry_ids) - set(local_file_backups))

        self.logger.info(f'Found backup file entries {extra_backup_entries} that do not have local files')

        for backup in self.db_session.query(BackupEntry).filter(BackupEntry.id.in_(extra_backup_entries)):
            if not dry_run:
                self.os_client.object_delete(self.oci_namespace, self.oci_bucket, backup.uploaded_file_path)
                self.db_session.query(BackupEntry).filter_by(id=backup.id).delete()
                self.db_session.commit()
        return extra_backup_entries
