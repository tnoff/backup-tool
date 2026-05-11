# Changelog

All notable changes to backup-tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-05-10

### Added
- GitLab Release is now published automatically on each new tag, with release notes pulled from the matching CHANGELOG section
- Renovate MRs now bump CHANGELOG.md alongside VERSION via the shared bump-version template's BUMP_CHANGELOG option

### Changed
- Source tarballs attached to GitLab Releases now contain only the runnable package, alembic migrations, and install metadata (`LICENSE`, `pyproject.toml`, `VERSION`); tests, CI configs, and top-level docs are excluded via `.gitattributes`
