# Backup Tool


Encrypt and backup local files to Oracle Cloud Infrastructure (OCI) Object Storage.

## Overview

For each file specified, the backup tool will first calculate the md5 of the file, encrypt that file while also saving the md5 of the encrypted file, and then upload the encrypted file to OCI Object Storage.

The tool can also restore these files from OCI Object storage, by first downloading the encrypted file and then decrypting it.

### Encryption Method

The tool uses AES encryption in CBC mode. Files are encrypted using a random salt value and a passphrase supplied to the client.


### MD5 sums


MD5 sums are calculated throughout the process to ensure data integrity. The md5 sum of each local file path is saved in the database, to ensure the file is not backed up multiple times, as well as to ensure the tool can recognize the file has been modified. The `--overwrite` flag can be used to ensure that updates to local files are backed up.

The md5 of the corresponding encrypted file is also calculated and saved in the database. When encrypting a new local file, it will calculate the md5 sum and verify there are no existing uploads with the same md5, as to not have multiple uploads of the same file.

When uploading the file to object storage, the client passes in the md5 as a header to ensure the object storage client will error if the md5 of the uploaded file does not match the expected value.


### Database


The database is a simple sqlite file stored locally.


## Install client


```
$ git clone https://github.com/tnoff/backup-tool.git
$ pip install backup-tool/
```

## Steps to Setup OCI


Helpful pages:

* https://docs.cloud.oracle.com/iaas/Content/API/Concepts/apisigningkey.htm
* https://docs.cloud.oracle.com/iaas/Content/API/Concepts/sdkconfig.htm

```
# Generate private and public key
$ mkdir ~/.oci
$ openssl genrsa -out ~/.oci/oci_api_key.pem 2048
$ openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
# Get pub key fingerprint and save
$ openssl rsa -pubout -outform DER -in ~/.oci/oci_api_key.pem | openssl md5 -c
# Install oci cli
$ pip install oci-cli
# Fix key permissions
$ oci setup repair-file-permissions --file ~/.oci/config
$ oci setup repair-file-permissions --file ~/.oci/oci_api_key.pem
```

Set up config in `~/.oci/config`

```
[DEFAULT]
user=<user-ocid>
fingerprint=<key-fingerprint>
region=us-ashburn-1
tenancy=<tenancy-ocid>
key_file=~/.oci/oci_api_key.pem
```


### Setup Compartments and Buckets


Generate compartment for backup data

```
$ oci iam compartment create -c "${TENANCY_OCID}" --name "backup" --description "Backup data"
```

Get compartment OCID and create bucket

```
$ backup=$(oci iam compartment list --all | jq -r '.data | .[] | select(.name=="backup") | .id')
$ oci os bucket create --name "data" --compartment-id "${backup}"
```

## Crypto Key

To encrypt and decrypt file, you'll need a crypto key. The crypto key can be any valid string including letters, numbers, and special characters. The length of the crypto key must be either 16, 24 or 32 bytes long.

```
$ cat .backup-tool/crypto-key
1234567890123456
```
## Config File

You can define common config options in a config file, by default the client will expect the config file in `~/.backup-tool/config`.

All options in the config file can be overridden by the cli.

The following is an example config file:

```
general:
  database_file: /home/user/.backup-tool/database.sql
  logging_file: /home/user/.backup-tool/backup-tool.log
  crypto_key_file: /home/user/.backup-tool/crypto-key
  relative_path: /home/user
  work_directory: /home/user/.backup-tool/work

oci:
  config_file: /home/user/.oci/config
  config_section: DEFAULT
  namespace: my-custom-namespace
  bucket: backup
```


### Database file


Path to the sqlite database.


### Logging

Path to logging file, by default the client will log debug to the log file and info to the console.


### Relative Path


Relative path prefix to remove from file path when stored in database. When restoring files this will be used as a prefix for files.

For example, if a relative path `/home/user` is used, and a file `/home/user/foo/bar` is backed up, the database will save its path as `foo/bar`

Then, when the file is restored, the path will joined with the relative path, to make `/home/user/foo/bar` again.


### Symlink Handling

When backing up directories, the tool follows symlinks to their resolved paths. However, symlinks are skipped to avoid backing up symlink files themselves. If you need to back up the target of a symlink, back up the target directory directly.


### Work Directory

The work directory is used for temporary files during encryption/decryption operations and for caching backup state. Configure it in the config file under `general.work_directory`. If not specified, a temporary directory is created and cleaned up after each run.

### Caching

For directory backups, you can use the `--cache-file` option to persist backup state across runs. The cache tracks:
- Files already encrypted and pending upload
- Files successfully processed

This allows resuming interrupted directory backups. If `--cache-file` is not specified, a cache file will be created in the work directory but will be lost when the work directory is cleaned up.

Example:
```
$ backup-tool directory backup --dir-paths /path/to/dir --cache-file ~/.backup-tool/cache.json
```


### Object Storage Options


Desired namespace and bucket of backup.


## Usage

To backup a single file:

```
$ backup-tool file backup path/to/file [--overwrite]
```

To backup an entire directory:

```
$ backup-tool directory backup --dir-paths path/to/dir [--overwrite]
```

To backup a directory, while skipping files:

```
$ backup-tool directory backup --dir-paths path/to/dir --skip-files "*.txt" [--overwrite]
```

To list local files:

```
$ backup-tool file list
```

To list uploaded backup files:

```
$ backup-tool backup list
```

To restore a file from backup:

```
$ backup-tool file restore <file-id>
```

Run cleanup to remove local file entries that no longer exist from the database:

```
$ backup-tool file cleanup [--dry-run]
```
 
Run cleanup to remove uploaded files that do not have a corresponding local file:

```
$ backup-tool backup cleanup [--dry-run]
```