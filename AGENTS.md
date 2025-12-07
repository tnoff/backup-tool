# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Backup tool for encrypting and uploading local files to Oracle Cloud Infrastructure (OCI) Object Storage. Files are encrypted using AES-CBC, tracked in a local SQLite database with MD5 checksums, and uploaded to OCI for backup/restore operations.

## Development Commands

### Testing
```bash
# Run all tests with tox (runs pylint + pytest with coverage)
tox

# Run tests for specific Python version
tox -e py312

# Run pytest directly (requires venv activation)
./venv/bin/python -m pytest tests/

# Run pytest with coverage
./venv/bin/python -m pytest --cov=backup_tool --cov-fail-under=75 tests/

# Run single test file
./venv/bin/python -m pytest tests/test_crypto.py
```

### Linting
```bash
# Run pylint (part of tox)
pylint backup_tool
```

### Installation
```bash
# Install in development mode
pip install -e .

# Install with venv
./venv/bin/pip install -e .
```

## Code Architecture

### Core Components

**backup_tool/client.py** - `BackupClient` class is the main orchestrator:
- Manages SQLite database session via SQLAlchemy
- Coordinates encryption, upload, and restore operations
- Handles file MD5 tracking to avoid duplicate uploads
- Uses work directory for temporary encrypted files

**backup_tool/database.py** - SQLAlchemy models:
- `BackupEntry`: Tracks uploaded files (one per unique encrypted file)
  - `uploaded_file_path`: UUID in object storage
  - `uploaded_md5_checksum`: MD5 of encrypted file
  - `original_md5_checksum`: MD5 of original file
- `BackupEntryLocalFile`: Tracks local file paths (many-to-one with BackupEntry)
  - `local_file_path`: Path on local filesystem
  - `backup_entry_id`: Foreign key to BackupEntry

**backup_tool/crypto.py** - AES encryption/decryption:
- `encrypt_file()`: AES-CBC encryption with random IV, returns both original and encrypted MD5
- `decrypt_file()`: Reverses encryption, validates MD5
- Uses pycryptodome library

**backup_tool/oci_client.py** - `OCIObjectStorageClient` wrapper:
- `object_put()`: Upload with multipart resume support
- `object_get()`: Download with archive restore support
- `object_list()`: List objects in bucket
- Supports both config file auth and instance principal auth

**backup_tool/cli/client.py** - `ClientCLI` class:
- Parses YAML config from `~/.backup-tool/config`
- Implements caching for directory backups (tracks pending uploads)
- Entry point: `backup-tool` command defined in setup.py

### Data Flow

**Backup Process:**
1. Calculate MD5 of local file
2. Check database for existing backup with same MD5 (skip if found unless --overwrite)
3. Encrypt file to work directory, get encrypted MD5
4. Check for duplicate encrypted MD5 (avoid duplicate uploads)
5. Generate UUID for object path
6. Upload encrypted file to OCI with MD5 validation
7. Create/update database entries linking local path to backup

**Restore Process:**
1. Query database for local file entry
2. Download encrypted file from OCI to work directory
3. Decrypt to final destination
4. Validate MD5 checksums

### Configuration

Config file at `~/.backup-tool/config` (YAML):
```yaml
general:
  database_file: /path/to/database.sql
  logging_file: /path/to/backup-tool.log
  crypto_key_file: /path/to/crypto-key  # 16, 24, or 32 byte passphrase
  relative_path: /home/user  # Prefix stripped/added for portability
  work_directory: /path/to/work/dir  # For temp files and caching

oci:
  config_file: /path/to/.oci/config
  config_section: DEFAULT
  namespace: oci-namespace
  bucket: backup-bucket
```

### Symlink Handling

**Important:** The directory backup traverses symlinks via `Path.resolve()` to get canonical paths. However, files that resolve outside the configured `relative_path` are skipped with a warning to prevent path resolution errors.

### Testing Requirements

- Minimum test coverage: 75%
- Tests must pass pylint with project-specific .pylintrc rules
- Supported Python versions: 3.10, 3.11, 3.12
- CI runs tox for all Python versions on pull requests
