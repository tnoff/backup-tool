import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backup_tool import crypto
from backup_tool.database import BASE, BackupEntry, BackupEntryLocalFile
from backup_tool.oci_client import ObjectStorageClient
from backup_tool import utils

def setup_logger(name, log_file_level, logging_file=None,
                 console_logging=True, console_logging_level=logging.INFO):
    logger = logging.getLogger(name)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    logger.setLevel(log_file_level)
    if logging_file is not None:
        fh = RotatingFileHandler(logging_file,
                                 backupCount=4,
                                 maxBytes=((2 ** 20) * 10))
        fh.setLevel(log_file_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    if console_logging:
        sh = logging.StreamHandler()
        sh.setLevel(console_logging_level)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger

class BackupClient():
    def __init__(self, database_file, crypto_key, oci_config_file, oci_config_section, oci_namespace, oci_bucket,
                 logging_file=None):

        self.logger = setup_logger('backup_client', 10, logging_file=logging_file)

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

        self.oci_namespace = oci_namespace
        self.oci_bucket = oci_bucket
        self.os_client = ObjectStorageClient(oci_config_file, oci_config_section)

    def file_backup(self, local_file, overwrite=True):
        '''
            Backup file to object storage

            local_file      :       Full path of local file
            overwrite       :       Upload new file is md5 is changed
        '''
        self.logger.info("Backing up local file:%s", local_file)

        # Keep boolean value to make sure we should upload new file
        upload_file = True

        # First check if local file exists, and if so, has md5 changed
        local_file_md5 = utils.md5(local_file)
        self.logger.debug("Local file %s md5 sum:%s", local_file, local_file_md5)

        local_backup_file = self.db_session.query(BackupEntryLocalFile).\
                filter(BackupEntryLocalFile.local_file_path == local_file).first()
        if local_backup_file:
            self.logger.debug("Found existing local file:%s", local_backup_file.id)
            if local_file_md5 == local_backup_file.local_md5_checksum:
                self.logger.debug("Existing local file has same md5")
                # Only upload if no backup file exists
                if local_backup_file.backup_entry_id is not None:
                    upload_file = False
            else:
                self.logger.debug("Existing local file has different md5 sum, updating")
                if overwrite is True:
                    local_backup_file.local_md5_checksum = local_file_md5
                    self.db_session.commit()
                    self.logger.debug("Updated local file %s to checksum %s",
                                      local_backup_file.id, local_file_md5)
                else:
                    upload_file = False

        else:
            self.logger.debug("No existing local file found for path:%s", local_file)
            backup_file_args = {
                'local_file_path': local_file,
                'local_md5_checksum' : local_file_md5,
            }

            local_backup_file = BackupEntryLocalFile(**backup_file_args)
            self.db_session.add(local_backup_file)
            self.db_session.commit()

        if upload_file:
            # Encrypt local file
            with utils.temp_file() as crypto_file:
                offset = crypto.encrypt_file(local_file, crypto_file, self.crypto_key)
                local_crypto_file_md5 = utils.md5(crypto_file)
                self.logger.debug("Created encrypted file %s from file %s with md5 %s",
                                  crypto_file, local_file, local_crypto_file_md5)

                # Check if md5 file already exists
                backup_entry = self.db_session.query(BackupEntry).\
                        filter(BackupEntry.uploaded_md5_checksum == local_crypto_file_md5).first()

                if backup_entry:
                    # If file exists, just upload local files data
                    self.logger.info("Encrypted upload with matching md5 found %s for file %s",
                                     backup_entry.id, local_file)
                    local_backup_file.backup_entry_id = backup_entry.id
                    self.db_session.commit()
                else:
                    # Else upload new file
                    self.logger.info("Now encrypted upload matching file %s, uploading copy",
                                     local_file)

                    # Make sure object path does not exist already
                    while True:
                        object_path = utils.random_string(length=1024)

                        existing_path = self.db_session.query(BackupEntry).\
                                filter(BackupEntry.uploaded_file_path == object_path).first()
                        if not existing_path:
                            break

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

    def file_list(self):
        local_files = []
        for local_file in self.db_session.query(BackupEntryLocalFile).all():
            local_files.append(local_file.as_dict())
        return local_files

    def backup_list(self):
        backup_files = []
        for backup_entry in self.db_session.query(BackupEntry).all():
            backup_files.append(backup_entry.as_dict())
        return backup_files