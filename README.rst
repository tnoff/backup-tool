###########
Backup Tool
###########

Encrypt and backup local files to Oracle Cloud Intrastructure (OCI) Object Storage.

========
Overview
========

For each file specified, the backup tool will first calculate the md5 of the file, encrypt that file while also saving the md5 of the encrypted file, and then upload the encrypted file to OCI Object Storage.

The tool can also restore these files from OCI Object storage, by first downloaded the encrypted file and then decrypting it.

-----------------
Encryption Method
-----------------

The tool uses a very basic AES encryption method that uses a single password (crypto key) to encrypt and decrypt files.

The tool will read a file in 16-byte intervals, and encrypt this into a 24-byte hash using the password specified.

If the last interval read from a file is not exactly 16-bytes, an "offset" of 0's will be added to the end of the interval before encryption. This offset is returned by the encryption method, and saved in the database for decryption. Decrypting a file will require specifying the offset for the file.

--------
MD5 sums
--------

MD5 sums are calculated throughout the process to ensure data integrity. The md5 sum of each local file path is saved in the database, to ensure the file is not backed up mutliple times, as well as to ensure the tool can recognize the file has been modified. The `--overwrite` flag can be used to ensure that updates to local files are backed up.

The md5 of the corresponding encrypted file is also cacluated and saved in the database. When encrypting a new local file, it will calculate the md5 sum and verify there are no existing uploads with the same md5, as to not have mutliple uploads of the same file.

When uploading the file to object storage, the client passes in the md5 as a header to ensure the object storage client will error if the md5 of the uploaded file does not match the expected value.

--------
Database
--------

The database is a simple sqlite file stored locally.

==============
Install client
==============

.. code-block:: none

    git clone https://github.com/tnoff/backup-tool.git
    pip install backup-tool/

==================
Steps to Setup OCI
==================

Helpful pages:

* https://docs.cloud.oracle.com/iaas/Content/API/Concepts/apisigningkey.htm
* https://docs.cloud.oracle.com/iaas/Content/API/Concepts/sdkconfig.htm


.. code-block:: none

    # Generate private and public key
    mkdir ~/.oci
    openssl genrsa -out ~/.oci/oci_api_key.pem 2048
    openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
    # Get pub key fingerprint and save
    openssl rsa -pubout -outform DER -in ~/.oci/oci_api_key.pem | openssl md5 -c
    # Install oci cli
    pip install oci-cli
    # Fix key permissions
    oci setup repair-file-permissions --file ~/.oci/config
    oci setup repair-file-permissions --file ~/.oci/oci_api_key.pem


Set up config in `~/.oci/config`

.. code-block:: none

    [DEFAULT]
    user=<user-ocid>
    fingerprint=<key-fingerprint>
    region=us-ashburn-1
    tenancy=<tenancy-ocid>
    key_file=~/.oci/oci_api_key.pem

------------------------------
Setup Compartments and Buckets
------------------------------

Generate compartent for backup data

.. code-block:: none

    ~>oci iam compartment create -c "${TENANCY_OCID}" --name "backup" --description "Backup data"

Get compartment OCID and create bucket

.. code-block:: none

    ~>backup=$(oci iam compartment list --all | jq -r '.data | .[] | select(.name=="backup") | .id')
    ~>oci os bucket create --name "data" --compartment-id "${backup}"

==========
Crypto Key
==========

To encrypt and decrypt file, you'll need a crypto key. The crypto key can be any valid string including letters, numbers, and special characters. The length of the crypto key must be a multiple of 16.

.. code-block:: none

    ~>cat .backup-tool/crypto-key
    1234567890123456

===========
Config File
===========

You can define common config options in a config file, by default the client will expect the config file in `~/.backup-tool/config`.

All options in the config file can be overriden by the cli.

The following is an example config file:

.. code-block:: none

    [general]

    database_file = /home/user/.backup-tool/database.sql
    logging_file = /home/user/.backup-tool/backup-tool.log
    crypto_key_file = /home/user/.backup-tool/crypto-key
    relative_path = /home/user

    [oci]
    config_file = /home/user/.oci/config
    config_stage = DEFAULT

    [object_storage]
    namespace = my-custom-namespace
    bucket_name = backup

-------------
Database file
-------------

Path to the sqlite database.

-------
Logging
-------

Path to logging file, by default the client will log debug to the log file and info to the console.

-------------
Relative Path
-------------

Relative path prefix to remove from file path when stored in database. When restoring files this will be used as a prefix for files.

For example, if a relative path `/home/user` is used, and a file `/home/user/foo/bar` is backed up, the database will save its path as `foo/bar`

Then, when the file is restored, the path will joined with the relative path, to make `/home/user/foo/bar` again.

----------------------
Object Storage Options
----------------------

Desired namespace and bucket of backup.

=====
Usage
=====

To backup a single file:

.. code-block:: none

    backup-tool file backup path/to/file [--overwrite]

To backup an entire directory:

.. code-block:: none

    backup-tool directory backup path/to/dir [--overwrite]

To backup a directory, while skipping files:

.. code-block:: none

    backup-tool directory backup path/to/dir --skip-files "*.txt" [--overwrite]

To list local files:

.. code-block:: none

    backup-tool file list

To list uploaded backup files:

.. code-block:: none

    backup-tool backup list

To restore a file from backup:

.. code-block:: none

    backup-tool file restore <file-id>
    
Run cleanup to remove local file entries that no longer exist from the database:

.. code-block:: none

    backup-tool file cleanup [--dry-run]
    
Run cleanup to remove uploaded files that do not have a corresponding local file:

.. code-block:: none

    backup-tool backup cleanup [--dry-run]
