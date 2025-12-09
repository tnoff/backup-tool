import os
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine, inspect, text

from backup_tool import utils
from backup_tool.client import BackupClient
from backup_tool.oci_client import ObjectStorageClient

# Needs to be 16 chars long
FAKE_CRYPTO_KEY = '1234567890123456'
FAKE_CONFIG = 'faker_config'
FAKE_SECTION = 'default'
FAKE_NAMESPACE = 'citadel'
FAKE_BUCKET = 'dragons'

class MockOSClient():
    def __init__(self, *args, **kwargs):
        pass

    def object_put(self, *args, **kwargs):
        return True

    def object_delete(self, *args, **kwargs):
        return True


def test_object_list(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            # Open file and write
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=124))
                client.file_backup(temp_file)
            # Should be one backup file with one local file
            file_list = client.file_list()
            assert len(file_list) == 1
            backup_list = client.backup_list()
            assert len(backup_list) == 1
            # Files should have diff md5s


def test_file_backup_overwrite(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=20))
                client.file_backup(temp_file)

                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=32))
                client.file_backup(temp_file, overwrite=True)

            # Should be one backup file with one local file
            file_list = client.file_list()
            assert len(file_list) == 1

            backup_list = client.backup_list()
            assert len(backup_list) == 2

            # Should be diff md5s
            assert backup_list[0]['uploaded_md5_checksum'] != backup_list[1]['uploaded_md5_checksum']

def test_file_restore(mocker):
    class MockOSGet():
        def __init__(self, *args, **kwargs):
            pass
        def object_put(self, *args, **kwargs):
            return True

        def object_get(_namespace, _bucket, _object_name, file_name, **kwargs):
            with open(file_name, 'w') as writer:
                # 'foo' encrypted
                writer.write('07BzhNET7exJ6qYjitX/AA==')
            return True

    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSGet)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('foo')
                client.file_backup(temp_file)

            local_file = client.file_list()[0]

            # Make sure file not there currently
            assert os.path.isfile(local_file['local_file_path']) == False

            # Attempt to download file again, will fail if md5 doesnt match
            with utils.temp_file(tmp_dir, name=local_file['local_file_path']) as temp_file:
                client.file_restore(local_file['id'])

def test_file_encrypt(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            with utils.temp_file(tmp_dir) as temp_file_input:
                # Write some dummy data to file
                with open(temp_file_input, 'w') as writer:
                    writer.write('1234567890123456')
                with utils.temp_file(tmp_dir) as temp_file_output:
                    client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                        FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

                    result = client.file_encrypt(temp_file_input, temp_file_output)
                    assert result['original_md5'] == 'q+rAfTwowb755zAALHU+1A=='

def test_file_decrypt(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            with utils.temp_file(tmp_dir) as temp_file_input:
                # Write some dummy data to file
                with open(temp_file_input, 'wb') as writer:
                    writer.write(b'\x10\x00\x00\x00\x00\x00\x00\x00\x0f\xc7\x9a\x8f\x0b\x89\xaf\xc9~\xbc\x1b)\xe7\xaa,R\x05H\xa5\x9f\x89\x00\xd3\xeb\x8ee\xec\xc64\xbd\x1b(')
                with utils.temp_file(tmp_dir) as temp_file_output:
                    result = client.file_decrypt(temp_file_input, temp_file_output)
                    print(result)

                    with open(temp_file_output, 'r') as reader:
                        read_data = reader.read()
                    assert read_data == '1234567890123456'

def test_file_cleanup(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            # First upload temp file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=20))
                client.file_backup(temp_file)

            # Now run file cleanup since temp file is deleted
            client.file_cleanup()

            # Test file list is empty
            file_list = client.file_list()
            assert len(file_list) == 0

            # Test backup file still exists
            backup_list = client.backup_list()
            assert len(backup_list) == 1

def test_backup_cleanup(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)
            # First upload temp file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=20))
                client.file_backup(temp_file)

            # Now run file cleanup since temp file is deleted
            client.file_cleanup()

            # Make sure backup list not empty
            backup_list = client.backup_list()
            assert len(backup_list) == 1

            # Now run backup cleanup
            client.backup_cleanup()

            # Make sure backup list is empty
            backup_list = client.backup_list()
            assert len(backup_list) == 0

def test_alembic_migrations(mocker):
    '''Test that Alembic migrations are run automatically'''
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            # Create a BackupClient which should run migrations
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Verify the alembic_version table exists
            engine = create_engine(f'sqlite:///{temp_db}')
            inspector = inspect(engine)
            tables = inspector.get_table_names()

            # Should have the alembic_version table along with our model tables
            assert 'alembic_version' in tables
            assert 'backup_entry' in tables
            assert 'backup_entry_local_file' in tables

            # Verify the migration was applied
            with engine.connect() as conn:
                result = conn.execute(text('SELECT version_num FROM alembic_version'))
                version = result.fetchone()[0]
                # Should be the latest migration (metadata caching)
                assert version == 'ff8c0e19188c'

def test_metadata_caching(mocker):
    '''Test that metadata caching speeds up backups for unchanged files'''
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Create a test file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('test content')

                # First backup - should calculate MD5 and cache metadata
                result = client.file_backup(temp_file)
                assert result == True

                # Get the database entry
                file_list = client.file_list()
                assert len(file_list) == 1

                # Verify metadata was cached
                local_file = file_list[0]
                assert local_file['cached_mtime'] is not None
                assert local_file['cached_size'] is not None

                # Second backup without changes - should skip due to metadata cache
                result = client.file_backup(temp_file)
                assert result == False  # File not backed up again

                # Verify we still have only one backup entry
                backup_list = client.backup_list()
                assert len(backup_list) == 1

def test_metadata_cache_detects_changes(mocker):
    '''Test that metadata cache detects when files change'''
    import time
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Create a test file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('original content')

                # First backup
                client.file_backup(temp_file)

                # Wait a moment and modify the file
                time.sleep(0.01)
                with open(temp_file, 'w') as writer:
                    writer.write('modified content with different size')

                # Second backup with overwrite - should detect change via metadata
                result = client.file_backup(temp_file, overwrite=True)
                assert result == True  # File was backed up again

                # Should have two backup entries now
                backup_list = client.backup_list()
                assert len(backup_list) == 2

def test_force_checksum_flag(mocker):
    '''Test that force_checksum flag forces MD5 calculation'''
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Create a test file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('test content')

                # First backup
                client.file_backup(temp_file)

                # Second backup with force_checksum - should calculate MD5 even though metadata unchanged
                # Should return False because MD5 matches
                result = client.file_backup(temp_file, force_checksum=True)
                assert result == False  # MD5 matched, so no new backup

                # Should still have only one backup entry
                backup_list = client.backup_list()
                assert len(backup_list) == 1

def test_metadata_cache_updates_after_backup(mocker):
    '''Test that metadata cache is updated after successful backup'''
    import time
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Create a test file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('original')

                # First backup
                client.file_backup(temp_file)
                original_list = client.file_list()
                original_mtime = original_list[0]['cached_mtime']

                # Modify file
                time.sleep(0.01)
                with open(temp_file, 'w') as writer:
                    writer.write('modified content')

                # Backup with overwrite
                client.file_backup(temp_file, overwrite=True)

                # Check that cached metadata was updated
                updated_list = client.file_list()
                updated_mtime = updated_list[0]['cached_mtime']

                # Metadata should have changed
                assert updated_mtime != original_mtime

def test_metadata_cache_populated_when_none(mocker):
    '''Test that metadata cache is populated even when initially None'''
    from backup_tool.database import BackupEntryLocalFile
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir, suffix='.sql') as temp_db:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, tmp_dir)

            # Create a test file
            with utils.temp_file(tmp_dir) as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('test content')

                # First backup
                client.file_backup(temp_file)

                # Manually clear the metadata cache to simulate old database entry
                file_list = client.file_list()
                assert len(file_list) == 1

                local_file = client.db_session.query(BackupEntryLocalFile).first()
                local_file.cached_mtime = None
                local_file.cached_size = None
                client.db_session.commit()

                # Verify metadata is None
                file_list = client.file_list()
                assert file_list[0]['cached_mtime'] is None
                assert file_list[0]['cached_size'] is None

                # Second backup - should calculate checksum and populate metadata
                result = client.file_backup(temp_file)
                assert result == False  # No new backup needed (MD5 matches)

                # Verify metadata was populated
                file_list = client.file_list()
                assert file_list[0]['cached_mtime'] is not None
                assert file_list[0]['cached_size'] is not None