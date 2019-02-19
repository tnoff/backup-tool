import codecs
from contextlib import contextmanager
import hashlib
import os
import random
import string

def random_string(length=32, prefix="", suffix=""):
    chars = string.ascii_lowercase + string.digits
    generated = "".join(random.choice(chars) for _ in range(length))
    return prefix + generated + suffix

@contextmanager
def temp_file(name=None, suffix='', delete=True):
    if not name:
        name = random_string(prefix='/tmp/', suffix=suffix)
    try:
        yield name
    finally:
        if delete:
            try:
                os.remove(name)
            except OSError as exc:
                if exc.errno == os.errno.ENOENT:
                    pass
                else:
                    raise

def md5(input_file):
    '''
    Get md5 base64 hash of input file
    '''
    hash_value = hashlib.md5()
    with open(input_file, 'rb') as read:
        while True:
            chunk = read.read(1024)
            if not chunk:
                break
            try:
                hash_value.update(chunk.encode('utf-8'))
            except AttributeError:
                # File is likely binary
                hash_value.update(chunk)
    md5_value = codecs.encode(hash_value.digest(), 'base64')
    return str(md5_value).rstrip("\\n'").lstrip("b'")
