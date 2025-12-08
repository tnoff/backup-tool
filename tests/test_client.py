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
                # Should be the initial migration
                assert version == 'ef9f78b6211b'