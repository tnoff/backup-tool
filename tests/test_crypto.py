import os
import unittest

from backup_tool import crypto
from backup_tool import utils


class TestCrypto(unittest.TestCase):
    def test_encyrpt_decrypt_file(self):
        # Generate passhparse
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                for _ in range(128):
                    random_string = utils.random_string(length=1024)
                    writer.write(random_string)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)


    def test_encyrpt_decrypt_file_binary(self):
        # Generate passhparse
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                for _ in range(128):
                    writer.write(os.urandom(1024))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)
