# AGENTS.md

Guidance for AI coding agents working in this repository. For user-facing
config schema and CLI usage see [README.md](README.md); for setup,
tests, linting, and Alembic migrations see [DEVELOPMENT.md](DEVELOPMENT.md).

## What this tool does

Encrypt local files with AES-CBC, track them in a local SQLite database
keyed by MD5, and store the ciphertext in OCI Object Storage. Supports
single-file and directory backups, content-addressed dedup, and restore
back to local disk.

## Architecture

### Core modules

| File | Role |
|---|---|
| `backup_tool/client.py` | `BackupClient` — orchestrates encrypt → upload → DB writes; restore is the reverse |
| `backup_tool/database.py` | SQLAlchemy models (`BackupEntry`, `BackupEntryLocalFile`) |
| `backup_tool/crypto.py` | `encrypt_file` / `decrypt_file` — AES-CBC, random IV, returns plaintext + ciphertext MD5 (pycryptodome) |
| `backup_tool/oci_client.py` | `OCIObjectStorageClient` — `object_put` (multipart resume), `object_get` (archive restore), `object_list`; config-file or instance-principal auth |
| `backup_tool/utils.py` | Path/MD5 helpers shared by client and CLI |
| `backup_tool/exception.py` | Custom exception hierarchy |
| `backup_tool/cli/client.py` | `ClientCLI` — YAML config loader, directory-cache logic, `backup-tool` entry point |
| `backup_tool/cli/common.py` | Shared CLI helpers (arg parsing, config resolution) |
| `alembic/` | Schema migrations; revisions live under `versions/` |

### Database

| Model | Key columns | Notes |
|---|---|---|
| `BackupEntry` | `id`, `uploaded_file_path` (UUID), `uploaded_md5_checksum`, `original_md5_checksum`, `cached_mtime`, `cached_size` | One row per unique encrypted file; dedup happens by `original_md5_checksum` |
| `BackupEntryLocalFile` | `id`, `local_file_path`, `backup_entry_id` (FK) | Many-to-one — same backup can satisfy multiple local paths |

`cached_mtime` / `cached_size` were added in revision
`ff8c0e19188c_add_cached_mtime_and_size_columns_for_*`. They short-circuit
the MD5 recompute for unchanged files during directory walks — if you
touch the DB models, leave these fields alone unless you're also
updating the directory-backup cache logic in `cli/client.py`.

## Data flow

### Backup

1. Compute MD5 of local file.
2. Skip if an existing `BackupEntry` matches that `original_md5_checksum`
   (unless `--overwrite`).
3. Encrypt to the configured `work_directory`; capture the ciphertext
   MD5.
4. Skip if the ciphertext MD5 already exists (a second guard against
   duplicate uploads).
5. Mint a UUID, upload to OCI with MD5 validation header.
6. Insert/refresh `BackupEntry` and link the local path via
   `BackupEntryLocalFile`.

### Restore

1. Look up the local path → `BackupEntry` row.
2. Download the encrypted blob to `work_directory`.
3. Decrypt to the final destination; validate the plaintext MD5
   against the stored value.

## Non-obvious internals

### Symlink resolution + the `relative_path` guard

Directory backup resolves every symlink with `Path.resolve()` to get a
canonical absolute path. Anything that resolves **outside** the
configured `relative_path` is skipped with a warning. This prevents
backing up arbitrary files reachable via symlink from inside the
backup root. Don't relax this — losing the bound makes the tool
silently follow symlinks into `/etc`, `/proc`, etc.

### `relative_path` is also a portability hinge

The same `relative_path` is **stripped** from `local_file_path` on
backup and **prepended** on restore. This lets the same DB + bucket
roundtrip between machines with different home directories (e.g.
`/home/alice` ↔ `/Users/alice`).

### `work_directory` doubles as the directory-backup cache

`ClientCLI` writes pending-upload sentinels into `work_directory`
during a directory backup, so an interrupted run resumes mid-tree
without re-MD5-ing everything. Don't repurpose the directory or trim it
between runs without invalidating that cache.

### Coverage gate is **85%**

The old AGENTS doc claimed 75% — the gate is now `--cov-fail-under=85`
in `tox.ini`. New code paths need tests proportional to that.

### Python support is py311–py314

`tox.ini` declares py311–py314. Older minimums (3.10 etc.) are not
supported. If you add code using a newer stdlib feature (e.g.
`tomllib`, structural pattern matching), match it against the lowest
declared env.

## Config schema

YAML at `~/.backup-tool/config` (or the path passed to `-c`):

```yaml
general:
  database_file: /path/to/database.sql
  logging_file: /path/to/backup-tool.log
  crypto_key_file: /path/to/crypto-key  # 16, 24, or 32 bytes
  relative_path: /home/user             # see above
  work_directory: /path/to/work

oci:
  config_file: /path/to/.oci/config
  config_section: DEFAULT
  namespace: oci-namespace
  bucket: backup-bucket
```
