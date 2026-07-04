# Changelog

All notable changes to backup-tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.15] - 2026-07-04

### Changed

- Bumped sqlalchemy to v2.0.51

## [0.1.14] - 2026-07-04

### Changed

- Bumped oci to v2.181.0

## [0.1.13] - 2026-06-28

### Changed

- Bumped alembic to v1.18.5

## [0.1.12] - 2026-06-14

### Changed

- Bumped oci to v2.178.0

## [0.1.11] - 2026-06-03

### Changed

- Bumped oci to v2.177.0

## [0.1.10] - 2026-05-27

### Changed

- Bumped oci to v2.176.0

## [0.1.9] - 2026-05-25

### Changed

- Bumped sqlalchemy to v2.0.50

## [0.1.8] - 2026-05-19

### Changed

- Bumped oci to v2.175.0

## [0.1.7] - 2026-05-13

### Changed

- Bumped oci to v2.174.0

## [0.1.6] - 2026-05-10

### Added
- GitLab Release is now published automatically on each new tag, with release notes pulled from the matching CHANGELOG section
- Renovate MRs now bump CHANGELOG.md alongside VERSION via the shared bump-version template's BUMP_CHANGELOG option

### Changed
- Source tarballs attached to GitLab Releases now contain only the runnable package, alembic migrations, and install metadata (`LICENSE`, `pyproject.toml`, `VERSION`); tests, CI configs, and top-level docs are excluded via `.gitattributes`
