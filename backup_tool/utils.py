import codecs
from contextlib import contextmanager
import hashlib
import logging
from logging.handlers import RotatingFileHandler
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
        if delete and os.path.exists(name):
            os.remove(name)

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
    # This leaves "b'<hash> at beginning, so take out first two chars
    return str(md5_value).rstrip("\\n'")[2:]

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
