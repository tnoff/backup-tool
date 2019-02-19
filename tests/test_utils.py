import unittest

from backup_tool import utils


class TestCrypto(unittest.TestCase):
    def test_md5(self):
        # Hardcoded, this is what the base64 hash of foo is
        value = '07BzhNET7exJ6qYjitX/AA=='
        with utils.temp_file() as temp:
            with open(temp, 'w') as writer:
                writer.write('foo\n')
            md5_value = utils.md5(temp)
        self.assertEqual(md5_value, value)
