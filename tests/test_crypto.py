import os
from tempfile import TemporaryDirectory

from backup_tool import crypto
from backup_tool import utils


def test_encyrpt_file_md5():
    # Generate passhparse
    passphrase = utils.random_string(length=16)
    randomish_string = utils.random_string(length=20)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_file_md5_binary():
    # Generate passhparse
    passphrase = utils.random_string(length=16)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(16))
            orig_md5_sum = utils.md5(input_temp)
            print(f'Original md5 {orig_md5_sum}')

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                print(f'Encrypted md5 {encrypted_md5}')
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    print(f'Encrypted md5 should be {en_md5}')
                    print(f'Decrypted md5 should be {or_md5}')
                    print(f'Decrypted md5 is {decrypted_md5}')
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_file_md5_small_file():
    # File size less than 16

    # Generate passhparse
    passphrase = utils.random_string(length=16)
    randomish_string = utils.random_string(length=5)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_file_md5_spaces():
    # File size less than 16

    # Generate passhparse
    passphrase = utils.random_string(length=16)
    randomish_string = " " * 24

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'


def test_encyrpt_file_md5_binary_larger_file():
    # Generate passhparse
    passphrase = utils.random_string(length=16)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(100))
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_empty_file():
    # Generate passhparse
    passphrase = utils.random_string(length=16)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'a'):
               os.utime(input_temp, None)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_file_md5_large_text():
    # Generate passhparse
    passphrase = utils.random_string(length=16)
    randomish_string = utils.random_string(length=102400)

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'

def test_encyrpt_file_md5_trail_spaces():
    # Generate passhparse
    passphrase = utils.random_string(length=16)
    randomish_string = utils.random_string(length=1024) + ' ' * 5

    with TemporaryDirectory() as tmp_dir:
        with utils.temp_file(tmp_dir) as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            orig_md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file(tmp_dir) as encrypted:
                or_md5, en_md5 = crypto.encrypt_file(input_temp, encrypted, passphrase)
                assert or_md5 == orig_md5_sum, 'Encryption returns wrong md5 value for original file'
                encrypted_md5 = utils.md5(encrypted)
                assert en_md5 == encrypted_md5, 'Encryption return wrong md5 value for encrypted file'

                with utils.temp_file(tmp_dir) as decrypted:
                    en_md5, or_md5 = crypto.decrypt_file(encrypted, decrypted, passphrase)
                    decrypted_md5 = utils.md5(decrypted)
                    assert decrypted_md5 == orig_md5_sum, 'MD5 of decrypted file does not match original'
                    assert en_md5 == encrypted_md5, 'Decryption returns wrong md5 value for original file'
                    assert or_md5 == orig_md5_sum, 'Decryption returns wrong md5 value for decrypted file'