# Development

Setup, tests, and Alembic migrations for working in this repo.
User-facing config and CLI usage live in [README.md](README.md); for
agent-facing internals see [AGENTS.md](AGENTS.md).

## Setup

Use a virtualenv:

```bash
virtualenv venv
source venv/bin/activate
pip install -e ".[test]"
```

## Tests

Full suite (pylint + bandit + pytest with 85% coverage gate) across
py311–py314:

```bash
tox
```

Single Python version:

```bash
tox -e py312
```

Tests only:

```bash
pytest tests/
```

Coverage report:

```bash
pytest --cov=backup_tool --cov-report=html --cov-fail-under=85 tests/
# open htmlcov/index.html
```

One file or test:

```bash
pytest tests/test_crypto.py
pytest tests/test_crypto.py::test_encrypt_file
```

## Linting and security

```bash
pylint backup_tool
bandit -r backup_tool
```

Both run inside `tox` and must pass for release.

## Alembic migrations

The SQLite schema is managed by Alembic
([alembic.ini](alembic.ini) + [alembic/](alembic/)).
The database URL comes from the running `BackupClient`, so set
`DATABASE_URL` (or pass `-x sqlalchemy.url=…`) before invoking Alembic
against a real DB:

```bash
# Apply latest schema
DATABASE_URL=sqlite:///path/to/db.sqlite alembic upgrade head

# Generate a new revision after editing backup_tool/database.py
DATABASE_URL=sqlite:///path/to/db.sqlite \
  alembic revision --autogenerate -m "description of change"
```

Existing revisions live under `alembic/versions/`. Review every
autogenerate result before committing — Alembic can't always infer
intent for column-type changes.

## Releasing

`VERSION` at the repo root is the source of truth. Bump it and push to
`main` — CI tags the commit and runs the publish pipeline via the
shared `tnoff-projects/github-workflows` templates.
