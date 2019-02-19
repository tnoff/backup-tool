#############################
Steps to Setup Authentication
#############################

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
