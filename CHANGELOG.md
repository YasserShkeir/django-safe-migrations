# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-15

### Added

- **Core Analysis Engine**: Static analysis system for Django migrations to detect unsafe operations without database connection.
- **Ruleset**: Implementing 17 safety rules (SM001-SM017):
  - SM001: `not_null_without_default` - Detects adding NOT NULL columns without defaults.
  - SM002-SM003: Unsafe column/table drops.
  - SM010-SM011: PostgreSQL concurrent index and constraint creation.
  - SM012: Enum value addition inside transactions (PostgreSQL).
  - SM007, SM016: Reversibility checks/warnings for RunSQL/RunPython.
- **Reporters**:
  - Console reporter with colorized output and safe fix suggestions.
  - JSON reporter for CI/CD pipeline integration.
  - GitHub Actions reporter for inline PR annotations.
- **Configuration**:
  - `SAFE_MIGRATIONS` Django setting for customizing rules (disable, severity overrides).
  - `check_migrations` management command with filters (`--new-only`, `--app`).
- **Documentation**:
  - Comprehensive documentation site using MkDocs.
  - [Comparison Guide](docs/comparison.md) vs `django-migration-linter` and `django-strong-migrations`.
  - Security audit and compliance tracking.
- **Testing & Quality**:
  - Docker-based integration testing suite supporting PostgreSQL and MySQL.
  - CI Matrix for Python 3.9-3.13 and Django 3.2-5.1.
  - Type hints (mypy) and linting (ruff/flake8) enforcement.

### Security

- Implemented detailed security documentation regarding `EXTRA_RULES` and dynamic code loading.
- Established security reporting policy.

[Unreleased]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YasserShkeir/django-safe-migrations/releases/tag/v0.1.0
