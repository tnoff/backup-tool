###########
Backup Tool
###########

Tool to backup local data to OCI.

The client will create local entries in a database, that will match to each unique file path. The client will track the files md5 sum as well.

For each unique local file md5, the client will upload an encrypted copy of that file to object storage. Note that if multiple files share the same md5, it will only upload that file once.

If requested, the client can restore files from object storage, by first downloading them to a temporary file, and then decrypting them.

==============
Install client
==============

.. code-block:: none

    git clone git@github.com:tnoff/backup-tool.git
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

To encrypt and decrypt file, you'll need a crypto key. The lenght of the crypto key must be a multiple of 16

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

    backup-tool file backup path/to/file

To backup an entire directory:

.. code-block:: none

    backup-tool directory backup path/to/dir

To backup a directory, while skipping files:

.. code-block:: none

    backup-tool directory backup path/to/dir --skip-files "*.txt"


To list local files:

.. code-block:: none

    backup-tool file list

To list backup files:

.. code-block:: none

    backup-tool backup list

To restore a file:

.. code-block:: none

    backup-tool file restore <file-id>
