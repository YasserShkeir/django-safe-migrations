# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.2] - 2026-02-12

### Fixed

- Fix KeyError when project contains squashed migrations (#33). The analyzer
  now reads migration objects directly from `disk_migrations` instead of
  `get_migration()` which relies on `graph.nodes` where replaced/squashed
  migrations may have been removed by Django's graph processing.

## [0.5.1] - 2026-02-08

### Documentation

- Updated all documentation files to reflect v0.5.0 features (SM028-SM036, baseline, diff, interactive, watch, verbose, GitLab reporter)
- Added 9 new rule sections to docs/rules.md (SM028-SM036)
- Updated docs/detected-patterns.md with SM028, SM030, SM033, SM035 examples
- Updated docs/configuration.md with new CLI options (--diff, --baseline, --interactive, --watch, --verbose, --list-rules)
- Updated docs/api.md with GitLabReporter, SarifReporter, and baseline/diff/interactive APIs
- Updated docs/ci_integration.md with GitLab Code Quality, diff mode, and baseline CI examples
- Updated docs/architecture.md with new modules (baseline.py, diff.py, interactive.py, watch.py, gitlab.py)
- Updated docs/quickstart.md and docs/troubleshooting.md with new features
- Updated docs/index.md feature list (36 rules, new modes)
- Added v0.5.0 and v0.6.0 roadmap documents

## [0.5.0] - 2026-02-05

### Added

- **9 New Rules** (SM028-SM036):
  - SM028: `prefer_bigint_over_int` — Warns when using 32-bit AutoField/IntegerField as primary key (WARNING)
  - SM029: `drop_not_null` — Warns when AlterField changes null=False to null=True (WARNING)
  - SM030: `require_concurrent_index_delete` — Detects RemoveIndex without CONCURRENTLY on PostgreSQL (ERROR)
  - SM031: `prefer_text_over_varchar` — Suggests TextField over CharField on PostgreSQL (INFO)
  - SM032: `prefer_timestamptz` — Warns about DateTimeField when USE_TZ=False (INFO)
  - SM033: `adding_field_with_default` — Warns about NOT NULL field with Python default causing row rewrite (WARNING)
  - SM034: `prefer_identity` — Suggests IDENTITY columns over SERIAL on PostgreSQL for Django < 4.0 (INFO)
  - SM035: `require_lock_timeout` — Suggests setting lock_timeout for DDL in RunSQL (INFO)
  - SM036: `prefer_if_exists` — Suggests IF [NOT] EXISTS for CREATE/DROP TABLE in RunSQL (INFO)

- **Baseline Support**: Generate and use baseline files to suppress existing issues:
  ```bash
  python manage.py check_migrations --generate-baseline .migration-baseline.json
  python manage.py check_migrations --baseline .migration-baseline.json
  ```

- **Diff Mode**: Only check migrations changed since a base branch:
  ```bash
  python manage.py check_migrations --diff
  python manage.py check_migrations --diff main
  ```

- **Interactive Mode**: Review issues one-by-one with keep/skip/fix/quit options:
  ```bash
  python manage.py check_migrations --interactive
  ```

- **Watch Mode**: Continuously watch migration files and re-run analysis on changes:
  ```bash
  pip install django-safe-migrations[watch]
  python manage.py check_migrations --watch
  ```

- **Verbose Mode**: Show progress information during analysis:
  ```bash
  python manage.py check_migrations --verbose
  ```

- **GitLab Code Quality Reporter**: Output in GitLab Code Quality format:
  ```bash
  python manage.py check_migrations --format=gitlab
  ```

### Changed

- **SM001**: UUIDField no longer unconditionally whitelisted; now requires explicit `default` or `db_default`
- **SM001**: Recognizes `db_default` (Django 5.0+) as a valid default
- **SM004**: Reduced false positives with before-state resolution for AlterField
- **SM012**: Regex narrowed to only match `ALTER TYPE ... ADD VALUE` pattern
- **SM013**: Before-state resolution prevents false positives on increasing max_length
- **SM019**: Removed non-reserved words from keyword list (`type`, `name`, `status`, etc.)
- **SM020**: Before-state resolution skips if field was already NOT NULL
- **SM021**: Before-state resolution skips if field was already unique
- **SM022**: Uses exact match instead of substring match for slow callables
- **SM024**: Patterns exclude LIKE and empty braces to reduce false positives
- **SM027**: Converted from standalone function to BaseRule subclass

### Fixed

- **SARIF reporter**: `helpUri` now points to valid docs URL; file paths are relative with `%SRCROOT%`
- **Console reporter**: Unicode symbols gracefully degrade on non-UTF-8 terminals
- **GitHub reporter**: Operation strings are properly escaped in annotation titles
- **JSON reporter**: Removed duplicate `_get_summary()`, reuses `MigrationAnalyzer.get_summary()`
- **PostGIS detection**: `postgis` vendor now correctly maps to `postgresql` rules
- **`get_db_vendor`**: Logs warning instead of silently returning `"unknown"` on error
- **SM023**: Removed dead `through != "auto"` branch
- **Suppression validation**: Warns on non-existent rule IDs in ignore comments

### Improved

- **Test quality**: Removed try/except/pass patterns, tautological assertions, and silent skips
- **Integration tests**: Proper assertions instead of catch-and-ignore patterns
- **Performance test thresholds**: Relaxed for CI runner variability

## [0.4.0] - 2026-01-20

### Added

- **8 New Rules**:
  - SM020: Detects `AlterField` with `null=False` without data backfill (ERROR)
  - SM021: Detects adding `unique=True` via `AlterField` which locks table (ERROR, PostgreSQL)
  - SM022: Warns about expensive callable defaults like `timezone.now` (WARNING)
  - SM023: Informational notice when adding `ManyToManyField` (INFO)
  - SM024: Detects SQL injection patterns in `RunSQL` operations (ERROR)
  - SM025: Warns about `ForeignKey` with explicit `db_index=False` (WARNING)
  - SM026: Warns about `RunPython` using `.all()` without batching (WARNING)
  - SM027: Detects missing merge migrations (multiple leaf nodes per app) (ERROR)

- **`--list-rules` Command**: List all available rules with severity, categories, and database support:

  ```bash
  python manage.py check_migrations --list-rules
  python manage.py check_migrations --list-rules --format=json
  ```

- **Configuration Validation**: Invalid rule IDs and category names are now validated on startup with typo suggestions:

  ```
  Configuration warning: Unknown rule ID in DISABLED_RULES: 'SM00'. Did you mean 'SM001'?
  ```

- **Custom Rule Plugin System**: Load custom rules via `EXTRA_RULES` setting:

  ```python
  SAFE_MIGRATIONS = {
      "EXTRA_RULES": [
          "myproject.rules.CustomRule",
      ]
  }
  ```

- **New Rule Categories**:
  - `relations`: Rules for foreign keys and many-to-many relationships
  - `security`: SQL injection detection rules
  - `performance`: Rules for expensive operations

- **Better CLI Help**: Added examples and documentation link to CLI epilog

### Changed

- **CI/CD Improvements**:
  - Updated `codecov/codecov-action` from v4 to v5
  - Added `pip-audit` security scanning job

### Documentation

- Updated rules index with new rules SM020-SM027
- Added custom rules documentation

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

[Unreleased]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.5.2...HEAD
[0.5.2]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/YasserShkeir/django-safe-migrations/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/YasserShkeir/django-safe-migrations/releases/tag/v0.1.0
