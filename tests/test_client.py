import os
from tempfile import TemporaryDirectory

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
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            # Open file and write
            with utils.temp_file() as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write(utils.random_string(length=124))
                client.file_backup(temp_file)
            # Should be one backup file with one local file
            file_list = client.file_list()
            assert len(file_list) == 1
            backup_list = client.backup_list()
            assert len(backup_list) == 1
            # Files should have diff md5s
            assert file_list[0]['local_md5_checksum'] != backup_list[0]['uploaded_md5_checksum']

def test_file_backup_same_md5s(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            randomish_string = utils.random_string()
            # Write same file and upload twice
            with utils.temp_file() as temp_file1:
                with open(temp_file1, 'w') as writer:
                    writer.write(randomish_string)
                client.file_backup(temp_file1)

                with utils.temp_file() as temp_file2:
                    with open(temp_file2, 'w') as writer:
                        writer.write(randomish_string)
                    client.file_backup(temp_file2)

            # Should be one backup file with one local file
            file_list = client.file_list()
            assert len(file_list) == 2
            assert file_list[0]['local_md5_checksum'] == file_list[1]['local_md5_checksum']

            backup_list = client.backup_list()
            assert len(backup_list) == 1

def test_file_backup_overwrite(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            with utils.temp_file() as temp_file:
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
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            with utils.temp_file() as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('foo')
                client.file_backup(temp_file)

            local_file = client.file_list()[0]

            # Make sure file not there currently
            assert os.path.isfile(local_file['local_file_path']) == False

            # Attempt to download file again, will fail if md5 doesnt match
            with utils.temp_file(name=local_file['local_file_path']) as temp_file:
                client.file_restore(local_file['id'])

def test_file_encrypt(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            with utils.temp_file() as temp_file_input:
                # Write some dummy data to file
                with open(temp_file_input, 'w') as writer:
                    writer.write('1234567890123456')
                with utils.temp_file() as temp_file_output:
                    client = BackupClient(temp_db, FAKE_CRYPTO_KEY, FAKE_CONFIG, FAKE_SECTION,
                                        FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)

                    result = client.file_encrypt(temp_file_input, temp_file_output)
                    assert result['offset'] == 0

                    with open(temp_file_output, 'r') as reader:
                        read_data = reader.read()
                    assert read_data == 'dXzNDNxckOrb7uz2ON0AAA=='

def test_file_decrypt(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            with utils.temp_file() as temp_file_input:
                # Write some dummy data to file
                with open(temp_file_input, 'w') as writer:
                    writer.write('dXzNDNxckOrb7uz2ON0AAA==')
                with utils.temp_file() as temp_file_output:
                    client.file_decrypt(temp_file_input, temp_file_output, 0)

                    with open(temp_file_output, 'r') as reader:
                        read_data = reader.read()
                    assert read_data == '1234567890123456'

def test_file_cleanup(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            # First upload temp file
            with utils.temp_file() as temp_file:
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
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            # First upload temp file
            with utils.temp_file() as temp_file:
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

def test_file_duplicates(mocker):
    mocker.patch('backup_tool.client.OCIObjectStorageClient',
                 return_value=MockOSClient)
    with utils.temp_file(suffix='.sql') as temp_db:
        with TemporaryDirectory() as temp_dir:
            client = BackupClient(temp_db, FAKE_CRYPTO_KEY, '', '', FAKE_NAMESPACE, FAKE_BUCKET, temp_dir)
            # First upload temp file
            with utils.temp_file() as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('abc')
                client.file_backup(temp_file)

            # Upload temp file of same data
            with utils.temp_file() as temp_file:
                with open(temp_file, 'w') as writer:
                    writer.write('abc')
                client.file_backup(temp_file)


            # Make sure there are two files, but one backup
            file_list = client.file_list()
            assert len(file_list) == 2

            backup_list = client.backup_list()
            assert len(backup_list) == 1

            # Now test duplicates
            duplicates = client.file_duplicates()
            # Make sure there is one key with a list of 2 items
            keys = list(duplicates.keys())
            assert len(keys) == 1

            assert len(duplicates[keys[0]]) == 2

