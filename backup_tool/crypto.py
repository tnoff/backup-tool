import codecs
import hashlib
import os
import struct

from Crypto.Cipher import AES

# https://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto
def encrypt_file(input_file, output_file, passphrase, chunksize=64*1024): #pylint:disable=too-many-locals
    '''
    Encrypts a file using AES (CBC mode) with the given key.

    input_file  :   Name of the input file
    output_file :   Name of output file
    passphrase  :   The encryption key - a string that must be either 16, 24 or 32 bytes long
    chunksize   :   Sets the size of the chunk which the function uses to read and encrypt the file
    '''
    iv = os.urandom(16)
    encryptor = AES.new(passphrase.encode('utf-8'), AES.MODE_CBC, iv)
    filesize = os.path.getsize(input_file)

    original_hash_value = hashlib.md5()
    encrypted_hash_value = hashlib.md5()
    with open(input_file, 'rb') as infile:
        with open(output_file, 'wb') as outfile:
            packed_qs = struct.pack('<Q', filesize)
            outfile.write(packed_qs)
            encrypted_hash_value.update(packed_qs)
            outfile.write(iv)
            encrypted_hash_value.update(iv)
            while True:
                chunk = infile.read(chunksize)
                if len(chunk) == 0:
                    break
                # Make sure we calculate has before trailing 0s are added
                original_hash_value.update(chunk)
                if len(chunk) % 16 != 0:
                    chunk += (' ' * (16 - len(chunk) % 16)).encode('utf-8')

                encrypted_chunk = encryptor.encrypt(chunk)
                encrypted_hash_value.update(encrypted_chunk)
                outfile.write(encrypted_chunk)
    original_md5_value = str(codecs.encode(original_hash_value.digest(), 'base64')).rstrip("\\n'")[2:]
    encrypted_md5_value = str(codecs.encode(encrypted_hash_value.digest(), 'base64')).rstrip("\\n'")[2:]
    return original_md5_value, encrypted_md5_value

def decrypt_file(input_file, output_file, passphrase, chunksize=24*1024): #pylint:disable=too-many-locals
    '''
    Decrypts a file using AES (CBC mode) with the given key.

    input_file  :   Name of the input file
    output_file :   Name of output file
    passphrase  :   The encryption key - a string that must be either 16, 24 or 32 bytes long
    chunksize   :   Sets the size of the chunk which the function uses to read and decrypt the file
    '''
    original_hash_value = hashlib.md5()
    decrypted_hash_value = hashlib.md5()
    with open(input_file, 'rb') as infile:
        read_input = infile.read(struct.calcsize('Q'))
        original_hash_value.update(read_input)
        origsize = struct.unpack('<Q', read_input)[0]

        iv = infile.read(16)
        original_hash_value.update(iv)

        decryptor = AES.new(passphrase.encode('utf-8'), AES.MODE_CBC, iv)
        total_size = 0
        with open(output_file, 'wb') as outfile:
            while True:
                chunk = infile.read(chunksize)
                if len(chunk) == 0:
                    break
                original_hash_value.update(chunk)
                decrypted_bit = decryptor.decrypt(chunk)
                # Check if current chunk is last chunk
                check_end = total_size + len(chunk) - origsize
                if check_end:
                    # Assume its last chunk
                    decrypted_bit = decrypted_bit[0:(-1 * ((total_size + len(chunk)) - origsize))]
                else:
                    total_size += len(chunk)
                outfile.write(decrypted_bit)
                decrypted_hash_value.update(decrypted_bit)
    original_md5_value = str(codecs.encode(original_hash_value.digest(), 'base64')).rstrip("\\n'")[2:]
    decrypted_md5_value = str(codecs.encode(decrypted_hash_value.digest(), 'base64')).rstrip("\\n'")[2:]
    return original_md5_value, decrypted_md5_value
