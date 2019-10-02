from Crypto.Cipher import AES
import base64


# https://stackoverflow.com/questions/519633/lazy-method-for-reading-big-file-in-python
def read_in_chunks(file_name, chunk_size=16):
    while True:
        data = file_name.read(chunk_size)
        if not data:
            break
        yield data

def encrypt_file(input_file, output_file, passphrase):
    cipher = AES.new(passphrase, AES.MODE_ECB)
    offset = 0
    with open(output_file, 'wb') as writer:
        with open(input_file, 'rb') as reader:
            for chunk in read_in_chunks(reader):
                if len(chunk) != 16:
                    # Possible last chunk not 16 bits in length
                    # When this happens, return offset that was added
                    # to make it 16 bits long, so that we know
                    # to remove it during decryption
                    offset = 16 - len(chunk)
                    chunk = chunk.ljust(16)
                encoded_bit = cipher.encrypt(chunk)
                encoded_chunk = base64.b64encode(encoded_bit)
                writer.write(encoded_chunk)
    return offset

def decrypt_file(input_file, output_file, passphrase, offset):
    cipher = AES.new(passphrase, AES.MODE_ECB)
    with open(output_file, 'wb') as writer:
        with open(input_file, 'rb') as reader:

            decoded_chunk = None
            decoded_bit = None
            while True:
                chunk = reader.read(24)
                if not chunk:
                    break
                if decoded_chunk is not None:
                    writer.write(decoded_chunk)
                decoded_bit = base64.b64decode(chunk)
                decoded_chunk = cipher.decrypt(decoded_bit)

            # Assume this is final part
            if offset:
                decoded_chunk = decoded_chunk[:-offset]
            if decoded_chunk != b'' and decoded_chunk is not None:
                writer.write(decoded_chunk)

    return True
