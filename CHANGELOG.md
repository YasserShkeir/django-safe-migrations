# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-01-20

### Added

- **New Rules**:
  - SM018: Detects `AddIndexConcurrently` / `RemoveIndexConcurrently` in atomic migrations (PostgreSQL). These operations require `atomic = False`.
  - SM019: Warns when column names are SQL reserved keywords (user, order, group, type, etc.).

- **Rule Categories**: Group related rules for bulk enable/disable:
  - Categories: `postgresql`, `indexes`, `constraints`, `destructive`, `locking`, `data-loss`, `reversibility`, `data-migrations`, `high-risk`, `informational`, `naming`, `schema-changes`
  - New settings: `DISABLED_CATEGORIES`, `ENABLED_CATEGORIES`

- **Per-App Configuration**: Configure rules differently per Django app via `APP_RULES` setting:
  - Per-app `DISABLED_RULES`, `DISABLED_CATEGORIES`, `ENABLED_CATEGORIES`
  - Per-app `RULE_SEVERITY` overrides

- **Debug Logging**: Comprehensive logging throughout the analyzer for troubleshooting. Enable with:
  ```python
  LOGGING = {
      'loggers': {
          'django_safe_migrations': {'level': 'DEBUG'},
      },
  }
  ```

### Changed

- **AST-Based Line Detection**: More accurate line number detection using Python AST parsing instead of bracket counting. Handles comments, multi-line strings, and complex formatting.

- **Smarter AlterField Detection (SM004)**: Reduced false positives by detecting safe changes:
  - Adding `null=True` (safe)
  - `TextField` alterations (usually metadata only)
  - `BooleanField` alterations (typically safe)

### Documentation

- Updated configuration guide with category and per-app settings.
- Added rule documentation for SM018 and SM019.
- Updated rules index with new rules.

## [0.2.0] - 2026-01-19

### Added

- **SARIF Reporter**: Output migration issues in SARIF 2.1.0 format for GitHub Code Scanning integration.
- **Inline Suppression Comments**: Suppress specific rules per-operation using `# safe-migrations: ignore SM001` comments.
- **Pre-commit Hook**: Official `.pre-commit-hooks.yaml` for repository-wide pre-commit integration.
- **Django Compatibility Documentation**: Dedicated page documenting version support and API differences.
- **Rule Documentation**: Comprehensive "Why Each Rule Exists" pages for all 17 rules (SM001-SM017).
- **Markdown Linting**: Added markdownlint and mdformat for consistent documentation formatting.

### Changed

- Management command now supports `--format=sarif` and `--output/-o` options for file output.

### Documentation

- Added GitHub Code Scanning integration guide.
- Added pre-commit hook integration guide.
- Added Safe Migration Patterns reference page.
- Added Detected Patterns guide showing what each rule looks for.
- Fixed ReadTheDocs navigation (added missing api.md, changelog.md, patterns.md).
- Fixed broken emoji encoding in README.md.
- Consolidated changelog files (docs/changelog.md now includes main CHANGELOG.md).

### Compatibility

- Tested against Django 3.2, 4.2, 5.0, 5.1, and 6.0.
- Tested against Python 3.9, 3.10, 3.11, 3.12, and 3.13.

## [0.1.2] - 2026-01-17

### Added

- Downloads badge in README (monthly stats from pepy.tech).
- Support section with sponsor link.
- GitHub FUNDING.yml for sponsor button.

### Changed

- Updated GitHub Actions: checkout v6, codeql-action v4, action-gh-release v2.
- Removed labels from dependabot.yml (labels did not exist in repo).

## [0.1.1] - 2026-01-16

### Added

- Support for Django 6.0 in metadata and testing matrix.

### Fixed

- **Compatibility**: Fixed `CheckConstraint` usage for Django 5.1+ (dynamically using `condition` instead of `check`).

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
  - Comparison Guide vs `django-migration-linter` and `django-strong-migrations`.
  - Security audit and compliance tracking.
- **Testing & Quality**:
  - Docker-based integration testing suite supporting PostgreSQL and MySQL.
  - CI Matrix for Python 3.9-3.13 and Django 3.2-5.1.
  - Type hints (mypy) and linting (ruff/flake8) enforcement.

### Security

- Implemented detailed security documentation regarding `EXTRA_RULES` and dynamic code loading.
- Established security reporting policy.

[Unreleased]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/YasserShkeir/django-safe-migrations/releases/tag/v0.1.0
