import os
import re
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backup_tool
from backup_tool import crypto
from backup_tool.database import BASE, BackupEntry, BackupEntryLocalFile
from backup_tool import utils

class BackupClient():
    def __init__(self, database_file, crypto_key, oci_config_file, oci_config_section, oci_namespace, oci_bucket,
                 logging_file=None, relative_path=None):

        self.logger = utils.setup_logger('backup_client', 10, logging_file=logging_file)

        if database_file is None:
            engine = create_engine('sqlite:///', encoding='utf-8')
            self.logger.debug("Initializing database with no file")
        else:
            engine = create_engine('sqlite:///%s' % database_file, encoding='utf-8')
            self.logger.debug("Initializing database with file:%s", database_file)

        BASE.metadata.create_all(engine)
        BASE.metadata.bind = engine
        self.db_session = sessionmaker(bind=engine)()

        self.crypto_key = crypto_key
        self.relative_path = relative_path

        self.oci_namespace = oci_namespace
        self.oci_bucket = oci_bucket
        self.os_client = backup_tool.oci_client.ObjectStorageClient(oci_config_file, oci_config_section, logger=self.logger)

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
            self.logger.warning("UUID %s already in use, generating another", object_path)


    def file_restore(self, local_file_id, overwrite=False):
        '''
            Restore file from object storage

            local_file_id   :   ID of local file database entry to restore locally
            overwrite       :   Overwrite local file if md5 does not match
        '''
        self.logger.info("Restoring local file:%s", local_file_id)

        local_file = self.db_session.query(BackupEntryLocalFile).get(local_file_id)
        if not local_file:
            self.logger.error("Unable to find local file:%s", local_file_id)
            return False

        if not local_file.backup_entry_id:
            self.logger.error("No backup entry for local file:%s", local_file_id)
            return False

        backup_entry = self.db_session.query(BackupEntry).get(local_file.backup_entry_id)

        if not backup_entry:
            self.logger.error("Expecting backup entry %s does not exist", local_file.backup_entry_id)

        local_file_path = local_file.local_file_path
        if self.relative_path:
            local_file_path = os.path.join(self.relative_path, local_file_path)

        if os.path.isfile(local_file_path):
            self.logger.debug("Checking local file %s md5", local_file_path)
            local_file_md5 = utils.md5(local_file_path)
            self.logger.debug("Local file %s has md5 sum %s", local_file_path, local_file_md5)
            if local_file.local_md5_checksum == local_file_md5:
                if not overwrite:
                    self.logger.info("Local file %s has expected md5 %s", local_file_path, local_file_md5)
                    return True

        # Write file to temp dir
        with utils.temp_file() as encrypted_file:
            self.logger.info("Downloading object %s to temp file %s", backup_entry.uploaded_file_path, encrypted_file)
            self.os_client.object_get(self.oci_namespace, self.oci_bucket,
                                      backup_entry.uploaded_file_path, encrypted_file)
            self.logger.info("Downloaded of object %s complete, written to temp file %s", backup_entry.uploaded_file_path, encrypted_file)

            # Check md5 matches expected
            self.logger.debug("Checking md5 sum of temp file %s", encrypted_file)
            downloaded_md5 = utils.md5(encrypted_file)
            self.logger.debug("Downloaded encrypted file %s has md5 sum %s", encrypted_file, downloaded_md5)
            if backup_entry.uploaded_md5_checksum != downloaded_md5:
                self.logger.error("Downloaded file %s has unexpected md5 %s, expected %s",
                                  encrypted_file, downloaded_md5, backup_entry.uploaded_md5_checksum)
                return True
            self.logger.debug("Decrypting temp file %s to file %s", encrypted_file, local_file_path)
            dir_name = os.path.dirname(local_file_path)
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            crypto.decrypt_file(encrypted_file, local_file_path, self.crypto_key,
                                backup_entry.uploaded_encryption_offset)


        # Check md5 matches expected
        self.logger.debug("Checking md5 of file %s", local_file_path)
        local_file_md5 = utils.md5(local_file_path)
        self.logger.debug("Local file %s has md5 sum %s", local_file_path, local_file_md5)
        if local_file_md5 != local_file.local_md5_checksum:
            self.logger.error("MD5 %s of decrypted file %s does not match expected %s",
                              local_file_md5, local_file_path, local_file.local_md5_checksum)
            return False
        return True


    def file_md5(self, local_file):
        '''
            Get md5sum of local file

            local_file      :       Full path of local file
        '''
        return utils.md5(local_file)

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

        self.logger.debug("Found existing local file:%s", local_backup_file.id)
        if local_file_md5 == local_backup_file.local_md5_checksum:
            self.logger.debug("Existing local file %s has expected md5 %s", local_file, local_file_md5)
            # Only upload if no backup file exists
            # If requested, check that backup file matches encryption
            if local_backup_file.backup_entry_id is not None and check_uploaded_md5 is False:
                upload_file = False
        else:
            self.logger.debug("Existing local file %s has unexpected  md5 sum %s", local_file, local_file_md5)
            if overwrite is True:
                local_backup_file.local_md5_checksum = local_file_md5
                # Current file has no backup, so set this to null for now
                local_backup_file.backup_entry_id = None
                self.db_session.commit()
                self.logger.debug("Updated local file %s to checksum %s",
                                  local_backup_file.id, local_file_md5)
            else:
                self.logger.warning("Overwrite set to false, not uploading new version of local file %s", local_file)
                upload_file = False
        return upload_file

    def _file_backup_upload(self, local_file, local_backup_file):
        with utils.temp_file() as crypto_file:
            self.logger.debug("Creating encrypted file %s from file %s",
                              crypto_file, local_file)
            offset = crypto.encrypt_file(local_file, crypto_file, self.crypto_key)
            self.logger.info("Created encrypted file %s from file %s with offset %s",
                             crypto_file, local_file, offset)
            self.logger.debug("Checking md5 sum of file %s", crypto_file)
            local_crypto_file_md5 = utils.md5(crypto_file)
            self.logger.info("Encrypted file %s has md5 sum %s", crypto_file, local_crypto_file_md5)

            # Check if md5 file already exists
            backup_entry = self.db_session.query(BackupEntry).\
                    filter(BackupEntry.uploaded_md5_checksum == local_crypto_file_md5).first()

            if backup_entry:
                # If file exists, just upload local files data
                self.logger.debug("Found existing upload with matching md5 found %s for file %s",
                                  backup_entry.id, local_file)
                local_backup_file.backup_entry_id = backup_entry.id
                self.db_session.commit()
                self.logger.info("Updated local file %s with backup entry %s", local_backup_file.id, backup_entry.id)
                return True

            # Else upload new file
            self.logger.info("No encrypted upload matching file with md5 %s, uploading copy",
                             local_crypto_file_md5)

            object_path = self._generate_uuid()

            self.logger.debug("Uploading encrypted file %s to object path %s",
                              crypto_file, object_path)
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
        self.logger.info("Uploaded encrypted file %s as backup entry %s",
                         crypto_file, backup_entry.id)

        local_backup_file.backup_entry_id = backup_entry.id
        self.db_session.commit()
        self.logger.info("Updated local backup %s to match backup entry %s",
                         local_backup_file.id, backup_entry.id)
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
        self.logger.info("Backing up local file:%s", local_file)
        if local_file_path != local_file:
            self.logger.debug("Using relative path for database %s", local_file_path)


        # First check if local file exists, and if so, has md5 changed
        self.logger.debug("Checking md5 sum for local file %s", local_file)
        local_file_md5 = utils.md5(local_file)
        self.logger.debug("Local file %s md5 sum:%s", local_file, local_file_md5)

        local_backup_file = self.db_session.query(BackupEntryLocalFile).\
                filter(BackupEntryLocalFile.local_file_path == local_file_path).first()
        if local_backup_file:
            upload_file = self._file_backup_file_exists(local_backup_file, local_file,
                                                        local_file_md5, overwrite, check_uploaded_md5)
        else:
            upload_file = True
            self.logger.debug("No existing local file found for path:%s", local_file)
            backup_file_args = {
                'local_file_path': local_file_path,
                'local_md5_checksum' : local_file_md5,
            }

            local_backup_file = BackupEntryLocalFile(**backup_file_args)
            self.db_session.add(local_backup_file)
            self.db_session.commit()
            self.logger.info("Created database entry %s for local file %s", local_backup_file.id, local_file)

        if upload_file:
            return self._file_backup_upload(local_file, local_backup_file)
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

    def directory_backup(self, dir_path, overwrite=False, check_uploaded_md5=False,
                         skip_files=None):
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

        for dir_name, _, file_list in os.walk(directory_path):
            # Check if dir matches skip files
            skip_dir = False
            for skip_check in skip_files:
                if re.match(skip_check, dir_name):
                    self.logger.warning("Ignoring dir %s since matches skip check %s", dir_name, skip_check)
                    skip_dir = True
                    break
            if skip_dir:
                continue
            self.logger.info("Backing up directory %s", dir_name)
            for file_name in file_list:
                full_path = os.path.join(dir_name, file_name)
                # Skip if matches any continue
                skip = False
                for skip_check in skip_files:
                    if re.match(skip_check, full_path):
                        self.logger.warning("Ignoring file %s since matches skip check %s", full_path, skip_check)
                        skip = True
                        break
                if not skip:
                    self._file_backup(full_path,
                                      overwrite=overwrite,
                                      check_uploaded_md5=check_uploaded_md5)

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
                self.logger.info("Local file %s path %s no longer present, removing from db", local_file.id, local_file_path)
                if not dry_run:
                    self.db_session.query(BackupEntryLocalFile).filter_by(id=local_file.id).delete()
                    self.db_session.commit()
                files_cleaned.append(local_file.id)
            else:
                self.logger.debug("Local file %s path %s exists, skipping", local_file.id, local_file_path)
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

        self.logger.info("Found backup file entries %s that do not have local files", extra_backup_entries)

        for backup in self.db_session.query(BackupEntry).filter(BackupEntry.id.in_(extra_backup_entries)):
            if not dry_run:
                self.os_client.object_delete(self.oci_namespace, self.oci_bucket, backup.uploaded_file_path)
                self.db_session.query(BackupEntry).filter_by(id=backup.id).delete()
                self.db_session.commit()
        return extra_backup_entries
