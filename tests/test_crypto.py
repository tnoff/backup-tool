import os
import unittest

from backup_tool import crypto
from backup_tool import utils


class TestCrypto(unittest.TestCase):
    def test_encyrpt_decrypt_file(self):
        # Generate passhparse
        passphrase = utils.random_string(length=16)
        randomish_string = utils.random_string(length=20)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)


    def test_encyrpt_decrypt_file_binary(self):
        # Generate passhparse
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(35))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_file_copy(self):
        passphrase = utils.random_string(length=16)

        randomish_string = utils.random_string(length=40)

        # Write same file twice
        with utils.temp_file() as input_temp1:
            with open(input_temp1, 'w') as writer:
                writer.write(randomish_string)
            md5_sum1 = utils.md5(input_temp1)

            with utils.temp_file() as input_temp2:
                with open(input_temp2, 'w') as writer:
                    writer.write(randomish_string)
                md5_sum2 = utils.md5(input_temp2)

                # Make sure file is same
                self.assertEqual(md5_sum1, md5_sum2)
                # Make sure encrypting both files gets same results
                with utils.temp_file() as encrypted1:
                    offset1 = crypto.encrypt_file(input_temp1, encrypted1, passphrase)
                    md5_sum1 = utils.md5(encrypted1)
                    with utils.temp_file() as encrypted2:
                        offset2 = crypto.encrypt_file(input_temp2, encrypted2, passphrase)
                        md5_sum2 = utils.md5(encrypted2)

                        # Make sure file is same
                        self.assertEqual(md5_sum1, md5_sum2)
                        self.assertEqual(offset1, offset2)

    def test_encrypt_small_file(self):
        # File size <16
        passphrase = utils.random_string(length=16)
        randomish_string = utils.random_string(length=3)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_spaces(self):
        passphrase = utils.random_string(length=16)
        randomish_string = " " * 24 

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_magic_number_16(self):
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(16))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_magic_number_20(self):
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(20))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_empty_file(self):
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'a'):
                os.utime(input_temp, None)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_largish_file(self):
        passphrase = utils.random_string(length=16)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(10240))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_largish_file_text(self):
        passphrase = utils.random_string(length=16)
        randomish_string = utils.random_string(length=204800)

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'w') as writer:
                writer.write(randomish_string)
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)

    def test_encrypt_trail_spaces(self):
        passphrase = utils.random_string(length=16)

        randomish_string = '0123456789' + ' ' * 2

        with utils.temp_file() as input_temp:
            # Write random data to file
            with open(input_temp, 'wb') as writer:
                writer.write(os.urandom(10240))
            # Get md5 sum of random file
            md5_sum = utils.md5(input_temp)

            # Ecnrypt and decrypt file, make sure md5 matches
            with utils.temp_file() as encrypted:
                offset = crypto.encrypt_file(input_temp, encrypted, passphrase)

                with utils.temp_file() as decrypted:
                    crypto.decrypt_file(encrypted, decrypted, passphrase, offset)

                    decrypted_md5 = utils.md5(decrypted)

            self.assertEqual(md5_sum, decrypted_md5)
