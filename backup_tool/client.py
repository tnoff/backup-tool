import uuid

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backup_tool import crypto
from backup_tool.exception import BackupToolClientException
from backup_tool.oci_client import OCIObjectStorageClient
from backup_tool.database import BASE, BackupEntry, BackupEntryLocalFile
from backup_tool import utils

class BackupClient():
    '''
    Backup Client
    '''
    def __init__(self, database_file, crypto_key, oci_config_file, oci_config_section, oci_namespace, oci_bucket,
                 work_directory, logging_file=None, relative_path=None, oci_instance_principal=False):
        '''
        Backup Client

        database_file   :   Path for sqlite database
        crypto_key      :   Crytography Passphrase
        oci_config_file :   Path of OCI Config File
        oci_config_section  : Path of OCI Config Section
        oci_namespace   :   OCI Object Storage Namespace
        oci_bucket      :   OCI Object Storage Bucket
        logging_file    :   Path for logging file
        work_directory  :   Directory for temporary files to be written to
        relative_path   :   Where files should be placed relative to machine
        Relative path explanation:
        If relative path given as "/home/user"

        If uploading file of path "/home/user/Documents/essay.txt", the relative path will be removed before adding the path to the database.
        This means the path stored in the database will be "Documents/essay.txt"

        Then when restoring files, the relative path will be added to the prefix of the files in the database.
        So if the database has "Documents/essay.txt", the full path of the restored file will be "/home/user/Documents/essay.txt"

        The basic idea here is to make moving files between different types of machines easier

        oci_instance_principal  : Use instance principal auth for client

        '''

        self.logger = utils.setup_logger('backup_client', 10, logging_file=logging_file)

        if database_file is None:
            engine = create_engine('sqlite:///')
            self.logger.debug('Initializing database with no file')
        else:
            engine = create_engine(f'sqlite:///{database_file}')
            self.logger.debug(f'Initializing database with file: "{database_file}"')

        BASE.metadata.create_all(engine)
        BASE.metadata.bind = engine
        self.db_session = sessionmaker(bind=engine)()

        self.crypto_key = crypto_key
        self.relative_path = None
        if relative_path:
            self.relative_path = Path(relative_path)

        self.work_directory = Path(work_directory)
        if not self.work_directory.exists():
            self.work_directory.mkdir(parents=True)

        self.oci_namespace = oci_namespace
        self.oci_bucket = oci_bucket
        if self.oci_namespace and self.oci_bucket:
            self.os_client = OCIObjectStorageClient(oci_config_file, oci_config_section,
                                                    instance_principal=oci_instance_principal, logger=self.logger)

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

    def file_restore(self, local_file_id, overwrite=False, set_restore=False): #pylint: disable=too-many-return-statements
        '''
        Restore file from object storage

        local_file_id   :   ID of local file database entry to restore locally
        overwrite       :   Overwrite local file if md5 does not match
        set_restore     :   If object is archived, attempt to restore
        '''
        self.logger.info(f'Restoring local file: {local_file_id}')

        local_file = self.db_session.get(BackupEntryLocalFile, local_file_id)
        if not local_file:
            self.logger.error(f'Unable to find local file: {local_file_id}')
            return False

        if not local_file.backup_entry_id:
            self.logger.error(f'No backup entry for local file: {local_file_id}')
            return False

        backup_entry = self.db_session.get(BackupEntry, local_file.backup_entry_id)

        if not backup_entry:
            self.logger.error(f'Expecting backup entry {local_file.backup_entry_id} does not exist')

        local_file_path = Path(local_file.local_file_path)
        if self.relative_path:
            local_file_path = self.relative_path / local_file_path

        if local_file_path.is_file():
            self.logger.debug(f'Checking local file "{str(local_file_path)}" md5')
            local_file_md5 = utils.md5(str(local_file_path))
            self.logger.debug(f'Local file "{str(local_file_path)}" has md5 sum {local_file_md5}')
            if backup_entry.original_md5_checksum == local_file_md5:
                if not overwrite:
                    self.logger.info(f'Local file "{str(local_file_path)}" has expected md5 {local_file_md5}')
                    return True

        # Write file to temp dir
        with utils.temp_file(self.work_directory) as encrypted_file:
            self.logger.info(f'Downloading object {backup_entry.uploaded_file_path} to temp file "{str(encrypted_file)}"')
            self.os_client.object_get(self.oci_namespace, self.oci_bucket,
                                      backup_entry.uploaded_file_path, str(encrypted_file), set_restore=set_restore)
            self.logger.info(f'Downloaded of object {backup_entry.uploaded_file_path} complete, written to temp file "{str(encrypted_file)}"')

            # Ensure dir of new decrypted file is created
            if not local_file_path.parent.exists():
                local_file_path.mkdir(parents=True)
            self.logger.debug(f'Decrypting temp file "{str(encrypted_file)}" to file "{str(local_file_path)}"')
            encrypted_file_md5, local_file_md5 = crypto.decrypt_file(str(encrypted_file),
                                                                     str(local_file_path),
                                                                     self.crypto_key)
            self.logger.debug(f'Decrypted file "{str(encrypted_file)}" with md5 "{encrypted_file_md5}" to '
                              f'file "{str(local_file_path)}" with md5 "{local_file_md5}"')
            if backup_entry.uploaded_md5_checksum != encrypted_file_md5:
                self.logger.error(f'Downloaded file "{str(encrypted_file)}" has unexpected md5 {encrypted_file_md5}, '
                                  f'expected {backup_entry.uploaded_md5_checksum}')
                return False

            if local_file_md5 != backup_entry.original_md5_checksum:
                self.logger.error(f'MD5 {local_file_md5} of decrypted file "{str(local_file_path)}" does not match expected {backup_entry.original_md5_checksum}')
                return False
        return True

    def file_md5(self, local_file):
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
        original_md5, encrypted_md5 = crypto.encrypt_file(local_input_file, local_output_file, self.crypto_key)
        self.logger.info(f'Encrypted local file "{local_input_file}" with md5 sum {original_md5} '
                         f' to output file "{local_output_file} with an md5 sum {encrypted_md5}')
        return {'encrypted_md5': encrypted_md5, 'original_md5': original_md5}

    def file_decrypt(self, local_input_file, local_output_file):
        '''
        Decrypt local file

        local_input_file    :   Full path of local input file
        local_ouput_file    :   Full path of local ouptut file
        '''
        original_md5, decrypted_md5 = crypto.decrypt_file(local_input_file, local_output_file, self.crypto_key)
        self.logger.info(f'Derypted local file "{local_input_file}" with md5 "{original_md5}" '
                         f'to output file "{local_output_file}" with md5 {decrypted_md5}')
        return {'original_md5': original_md5, 'decrypted_md5': decrypted_md5}

    def _check_backup_file_exists(self, local_backup_file, local_file_md5, overwrite):
        '''
        Local backup of file exists
        '''
        self.logger.debug(f'Found existing local file: {local_backup_file.id}')
        same_md5_backup_entry = self.db_session.query(BackupEntry).\
                                    filter(BackupEntry.original_md5_checksum == local_file_md5).first()

        # Check if backup entry already exists with checked md5, if so exit
        if not local_backup_file.backup_entry_id:
            # No backup file set yet, see if there is an existing file
            if same_md5_backup_entry:
                self.logger.debug(f'Updating local backup file {local_backup_file.id} to backup entry {same_md5_backup_entry.id}')
                local_backup_file.backup_entry_id = same_md5_backup_entry.id
                self.db_session.commit()
                return False
            return True

        # Check if backup entry matches local file
        backup_entry = self.db_session.get(BackupEntry, local_backup_file.backup_entry_id)
        if backup_entry.original_md5_checksum == local_file_md5:
            self.logger.debug(f'Local backup file {local_backup_file.id} still has same md5 as {backup_entry.id}')
            return False
        # MD5 sum does not match, but check if md5 is used
        if same_md5_backup_entry:
            self.logger.debug(f'Updating local backup file {local_backup_file.id} to backup entry {same_md5_backup_entry.id}')
            local_backup_file.backup_entry_id = same_md5_backup_entry.id
            self.db_session.commit()
            return False
        # Even if file is updated, if we dont have overwrite passed in, dont upload
        if not overwrite:
            self.logger.debug('Overwrite set to false, ignoring md5 mismatch')
            return False
        # Else assume not matching, need to upload
        local_backup_file.backup_entry_id = None
        self.db_session.commit()
        return True

    def _file_backup_ensure_database_entry(self, local_file_path, local_file_md5, overwrite):
        relative_file_path = local_file_path
        if self.relative_path:
            relative_file_path = local_file_path.relative_to(self.relative_path)
            self.logger.debug(f'Using relative path for database "{str(relative_file_path)}"')
        local_backup_file = self.db_session.query(BackupEntryLocalFile).\
            filter(BackupEntryLocalFile.local_file_path == str(relative_file_path)).first()
        if local_backup_file:
            return self._check_backup_file_exists(local_backup_file, local_file_md5, overwrite), local_backup_file

        self.logger.debug(f'No existing local file found for path: "{str(local_file_path)}"')
        backup_file_args = {
            'local_file_path': str(relative_file_path),
        }

        local_backup_file = BackupEntryLocalFile(**backup_file_args)
        self.db_session.add(local_backup_file)
        self.db_session.commit()
        self.logger.info(f'Created database entry {local_backup_file.id} for local file "{str(relative_file_path)}"')
        return True, local_backup_file

    def _file_backup_encrypt(self, local_file_path, local_file_md5):
        with utils.temp_file(self.work_directory, delete=False) as encrypted_file:
            self.logger.debug(f'Creating encrypted file "{str(encrypted_file)}" from file "{str(local_file_path)}"')
            check_local_file_md5, encrypted_file_md5 = crypto.encrypt_file(str(local_file_path), str(encrypted_file), self.crypto_key)
            if check_local_file_md5 != local_file_md5:
                self.logger.error(f'Unable to verify md5 during crypto phase for file "{str(local_file_path)}"')
                raise BackupToolClientException(f'Unable to verify md5 during crypto phase for file "{str(local_file_path)}"')
            self.logger.debug(f'Created encrypted file "{str(encrypted_file)}" with md5 "{encrypted_file_md5}" '
                            f' from original file "{str(local_file_path)}" with md5 "{local_file_md5}"')
            return {
                'local_file': str(local_file_path),
                'local_file_md5': local_file_md5,
                'encrypted_file': str(encrypted_file),
                'encrypted_file_md5': encrypted_file_md5,
            }

    def _file_backup_upload(self, encrypted_file, local_encrypted_file_md5, original_md5_checksum, local_backup_file, object_path=None, resume_upload=False):
        object_path = object_path or self._generate_uuid()
        self.logger.debug(f'Uploading encrypted file "{str(encrypted_file)}" to object path {object_path}')
        self.os_client.object_put(self.oci_namespace, self.oci_bucket, object_path, str(encrypted_file),
                                  md5_sum=local_encrypted_file_md5, resume_upload=resume_upload)

        backup_args = {
            'uploaded_file_path' : object_path,
            'uploaded_md5_checksum' : local_encrypted_file_md5,
            'original_md5_checksum':original_md5_checksum,
        }

        backup_entry = BackupEntry(**backup_args)
        self.db_session.add(backup_entry)
        self.db_session.commit()
        self.logger.info(f'Uploaded encrypted file "{str(encrypted_file)}" as backup entry {backup_entry.id}')

        local_backup_file.backup_entry_id = backup_entry.id
        self.db_session.commit()
        self.logger.info(f'Updated local backup {local_backup_file.id} to match backup entry {backup_entry.id}')
        return True

    def file_backup(self, local_file, overwrite=False):
        '''
        Backup file to object storage

        local_file                  :       Full path of local file
        overwrite                   :       Upload new file is md5 is changed
        automatically_upload_files  :       Upload new files automatically
        '''
        # Use local file as the full path of the file
        # Use local file path as relative path for the database
        local_file_path = Path(local_file).resolve()
        self.logger.info(f'Backing up local file: "{str(local_file_path)}"')
        local_file_md5 = utils.md5(local_file_path)
        self.logger.debug(f'Local file "{str(local_file_path)}" has md5 {local_file_md5}')
        should_upload_file, local_backup_file = self._file_backup_ensure_database_entry(local_file, local_file_md5, overwrite)
        if not should_upload_file:
            return False
        encryption_data = self._file_backup_encrypt(local_file_path, local_file_md5)
        self._file_backup_upload(encryption_data['encrypted_file'],
                                 encryption_data['encrypted_file_md5'],
                                 encryption_data['local_file_md5'],
                                 local_backup_file)
        Path(encryption_data['encrypted_file']).unlink()
        return True

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
            local_file_path = Path(local_file.local_file_path)
            if self.relative_path:
                local_file_path = self.relative_path / local_file_path
            if not local_file_path.exists():
                self.logger.info(f'Local file {local_file.id} path "{str(local_file_path)}" no longer present, removing from db')
                if not dry_run:
                    self.db_session.query(BackupEntryLocalFile).filter_by(id=local_file.id).delete()
                files_cleaned.append(local_file.id)
            else:
                self.logger.debug(f'Local file {local_file.id} path "{str(local_file_path)}" exists, skipping')
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
