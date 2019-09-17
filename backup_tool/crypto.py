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
    newline = bytearray()
    newline.extend(map(ord, '\n'))
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
                writer.write(newline)
    return offset

def decrypt_file(input_file, output_file, passphrase, offset):
    cipher = AES.new(passphrase, AES.MODE_ECB)
    # TODO probably expensive to read file twice here
    num_lines = sum(1 for line in open(input_file))
    with open(output_file, 'wb') as writer:
        with open(input_file, 'rb') as reader:
            for (count, line) in enumerate(reader.readlines()):
                line = line.decode('utf-8')
                decoded_bit = base64.b64decode(line)
                decoded_chunk = cipher.decrypt(decoded_bit)
                # If last line in file, is possible that offset
                # was added, if so, remove offset here
                if count == num_lines - 1:
                    decoded_chunk = decoded_chunk[:-offset]
                writer.write(decoded_chunk)
    return True

