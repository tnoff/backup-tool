import codecs
from contextlib import contextmanager
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import random
import string

from pathlib import Path

def random_string(length=32, prefix='', suffix=''):
    '''
    Generate random string

    length  :   Length of string
    prefix  :   Prefix to place before random characters
    suffix  :   Suffix to place after random characters
    '''
    chars = string.ascii_lowercase + string.digits
    generated = "".join(random.choice(chars) for _ in range(length - len(prefix) - len(suffix)))
    return f'{prefix}{generated}{suffix}'

@contextmanager
def temp_file(directory, name=None, suffix='', delete=True):
    '''
    Create temporary file

    name        :   Name of temporary file
    directory   :   Directory for temporary files
    suffix      :   Suffix for temporary file name ( not used if name given )
    delete      :   Delete file after use
    '''
    file_path = None
    directory = Path(directory)
    if not directory.exists():
        directory.mkdir(parents=True)
    if not name:
        file_path = directory / random_string(suffix=suffix)
    else:
        file_path = directory / name
    try:
        if file_path:
            yield Path(file_path)
        else:
            yield None
    finally:
        if delete and file_path and file_path.exists():
            file_path.unlink()

def md5(input_file, chunksize=64*1024):
    '''
    Get md5 base64 hash of input file
    '''
    hash_value = hashlib.md5()
    with open(input_file, 'rb') as read:
        while True:
            chunk = read.read(chunksize)
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
    '''
    Setup logging
    '''
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
