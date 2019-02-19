import pyAesCrypt

def encrypt_file(input_file, output_file, passphrase, buffer_size=64 * 1024):
    return pyAesCrypt.encryptFile(input_file, output_file, passphrase, buffer_size)


def decrypt_file(input_file, output_file, passphrase, buffer_size=64 * 1024):
    return pyAesCrypt.decryptFile(input_file, output_file, passphrase, buffer_size)
