# Django Safe Migrations

[![PyPI version](https://badge.fury.io/py/django-safe-migrations.svg)](https://badge.fury.io/py/django-safe-migrations)
[![Downloads](https://static.pepy.tech/badge/django-safe-migrations/month)](https://pepy.tech/project/django-safe-migrations)
[![CI](https://github.com/YasserShkeir/django-safe-migrations/actions/workflows/ci.yml/badge.svg)](https://github.com/YasserShkeir/django-safe-migrations/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YasserShkeir/django-safe-migrations/branch/main/graph/badge.svg)](https://codecov.io/gh/YasserShkeir/django-safe-migrations)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-safe-migrations.svg)](https://pypi.org/project/django-safe-migrations/)
[![Django Versions](https://img.shields.io/badge/django-3.2%20%7C%204.2%20%7C%205.0%20%7C%205.1%20%7C%206.0-blue.svg)](https://django-safe-migrations.readthedocs.io/en/latest/django-compatibility/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Detect unsafe Django migrations before they break production.**

Django Safe Migrations analyzes your Django migrations and warns you about operations that could cause downtime, lock tables, or cause data loss in production environments.

## Features

- **Detect unsafe operations** before they reach production ([see what we catch](https://django-safe-migrations.readthedocs.io/en/latest/detected-patterns/))
- **PostgreSQL-aware** rules for concurrent index creation and more
- **Clear fix suggestions** with safe migration patterns
- **Multiple output formats**: Console (with colors), JSON, GitHub Actions annotations, GitLab Code Quality, SARIF
- **Easy CI/CD integration** with GitHub Actions, pre-commit hooks, and GitHub Code Scanning
- **Configurable rules** to match your deployment strategy
- **Diff mode** — only check migrations changed since a branch
- **Baseline support** — suppress existing issues, catch only new ones
- **Interactive mode** — review issues one-by-one with keep/skip/fix/quit
- **Watch mode** — continuously re-run on file changes (requires watchdog)

## Rules

| Rule ID | Name                               | Severity | Description                                                 |
| ------- | ---------------------------------- | -------- | ----------------------------------------------------------- |
| SM001   | `not_null_without_default`         | ERROR    | Adding NOT NULL column without default will lock table      |
| SM002   | `drop_column_unsafe`               | WARNING  | Dropping column while old code may reference it             |
| SM003   | `drop_table_unsafe`                | WARNING  | Dropping table while old code may reference it              |
| SM004   | `alter_column_type`                | WARNING  | Changing column type may rewrite table                      |
| SM005   | `add_foreign_key_validates`        | WARNING  | FK constraint validates existing rows (locks)               |
| SM006   | `rename_column`                    | INFO     | Column rename may break old code during deployment          |
| SM007   | `run_sql_unsafe`                   | WARNING  | RunSQL without reverse_sql is not reversible                |
| SM008   | `large_data_migration`             | INFO     | Data migration may be slow on large tables                  |
| SM009   | `add_unique_constraint`            | ERROR    | Adding unique constraint requires full table scan           |
| SM010   | `index_not_concurrent`             | ERROR    | Index creation without CONCURRENTLY (PostgreSQL)            |
| SM011   | `unique_constraint_not_concurrent` | ERROR    | Unique constraint without concurrent index                  |
| SM012   | `enum_add_value_transaction`       | ERROR    | Adding enum value inside transaction (PostgreSQL)           |
| SM013   | `alter_varchar_length`             | WARNING  | Decreasing VARCHAR length rewrites table                    |
| SM014   | `rename_model`                     | WARNING  | Model rename may break FKs and external references          |
| SM015   | `alter_unique_together`            | WARNING  | Deprecated in favor of UniqueConstraint                     |
| SM016   | `run_python_no_reverse`            | INFO     | RunPython without reverse_code is not reversible            |
| SM017   | `add_check_constraint`             | WARNING  | Check constraint validates all existing rows                |
| SM018   | `concurrent_in_atomic_migration`   | ERROR    | Concurrent index operations require atomic=False            |
| SM019   | `reserved_keyword_column`          | INFO     | Column name is a reserved SQL keyword                       |
| SM020   | `alter_field_null_false`           | ERROR    | AlterField null=False without data backfill                 |
| SM021   | `alter_field_unique`               | ERROR    | Adding UNIQUE via AlterField on existing data               |
| SM022   | `expensive_default_callable`       | WARNING  | Default value uses expensive callable (e.g., now())         |
| SM023   | `add_many_to_many`                 | INFO     | ManyToMany creates junction table (potential locks)         |
| SM024   | `sql_injection_pattern`            | ERROR    | SQL injection patterns detected in RunSQL                   |
| SM025   | `fk_without_index`                 | WARNING  | Foreign key without db_index on large tables                |
| SM026   | `run_python_no_batching`           | WARNING  | RunPython using .all() without batching                     |
| SM027   | `missing_merge_migration`          | ERROR    | Multiple leaf migrations need merge migration               |
| SM028   | `prefer_bigint_over_int`           | WARNING  | Prefer BigAutoField over 32-bit AutoField primary keys      |
| SM029   | `drop_not_null`                    | WARNING  | Dropping NOT NULL constraint may allow unintended NULLs     |
| SM030   | `require_concurrent_index_delete`  | ERROR    | Index removal without CONCURRENTLY locks table (PostgreSQL) |
| SM031   | `prefer_text_over_varchar`         | INFO     | Consider TextField over CharField on PostgreSQL             |
| SM032   | `prefer_timestamptz`               | INFO     | DateTimeField without USE_TZ stores naive datetimes         |
| SM033   | `adding_field_with_default`        | WARNING  | NOT NULL field with Python default rewrites all rows        |
| SM034   | `prefer_identity`                  | INFO     | Consider IDENTITY columns on PostgreSQL (Django < 4.0)      |
| SM035   | `require_lock_timeout`             | INFO     | DDL in RunSQL should set lock_timeout                       |
| SM036   | `prefer_if_exists`                 | INFO     | Use IF [NOT] EXISTS in CREATE/DROP TABLE                    |

## Installation

```bash
pip install django-safe-migrations
```

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_safe_migrations',
]
```

## Usage

### Management Command

```bash
# Check all migrations
python manage.py check_migrations

# Check specific apps
python manage.py check_migrations myapp otherapp

# Only check unapplied migrations
python manage.py check_migrations --new-only

# JSON output for CI
python manage.py check_migrations --format=json

# GitHub Actions annotations
python manage.py check_migrations --format=github

# Fail on warnings too
python manage.py check_migrations --fail-on-warning

# GitLab Code Quality output
python manage.py check_migrations --format=gitlab

# Diff mode - only check changed migrations
python manage.py check_migrations --diff
python manage.py check_migrations --diff main

# Baseline - suppress existing issues
python manage.py check_migrations --generate-baseline .migration-baseline.json
python manage.py check_migrations --baseline .migration-baseline.json

# Interactive review
python manage.py check_migrations --interactive

# Verbose output
python manage.py check_migrations --verbose

# Watch mode (requires: pip install django-safe-migrations[watch])
python manage.py check_migrations --watch
```

### Example Output

```
Found 2 migration issue(s):

✖ ERROR [SM001] myapp/migrations/0002_add_email.py:15
   Adding NOT NULL field 'email' to 'user' without a default value will lock the table
   Operation: AddField(user.email)

   💡 Suggestion:
      Safe pattern for adding NOT NULL field:

      1. Migration 1 - Add field as nullable:
         migrations.AddField(
             model_name='user',
             name='email',
             field=models.CharField(max_length=255, null=True),
         )

      2. Data migration - Backfill existing rows in batches

      3. Migration 3 - Add NOT NULL constraint:
         migrations.AlterField(
             model_name='user',
             name='email',
             field=models.CharField(max_length=255, null=False),
         )

⚠ WARNING [SM002] myapp/migrations/0003_remove_old.py:10
   Dropping column 'old_field' from 'user' - ensure all code references have been removed first
   Operation: RemoveField(user.old_field)

──────────────────────────────────────────────────
Summary: 1 error(s), 1 warning(s)
```

## 🔄 CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/check-migrations.yml
name: Check Migrations

on:
  pull_request:
    paths:
      - "**/migrations/**"

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install django-safe-migrations Django

      - name: Check migrations
        run: python manage.py check_migrations --format=github --fail-on-warning
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations --new-only
        language: system
        types: [python]
        pass_filenames: false
```

## ⚙️ Configuration

### Command Options

| Option                     | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| `--format`                 | Output format: `console`, `json`, `github`, `gitlab`, `sarif` |
| `--output`, `-o`           | Output file path (defaults to stdout)                         |
| `--fail-on-warning`        | Exit with error code on warnings                              |
| `--new-only`               | Only check unapplied migrations                               |
| `--no-suggestions`         | Hide fix suggestions                                          |
| `--exclude-apps`           | Apps to exclude from checking                                 |
| `--include-django-apps`    | Include Django's built-in apps                                |
| `--diff [BASE_REF]`        | Only check migrations changed since BASE_REF (default: main)  |
| `--baseline FILE`          | Exclude issues present in baseline file                       |
| `--generate-baseline FILE` | Generate baseline file from current issues                    |
| `--interactive`            | Interactively review each issue                               |
| `--verbose`                | Show progress information during analysis                     |
| `--watch`                  | Watch migration files and re-run on changes                   |
| `--list-rules`             | List all available rules and exit                             |

### Programmatic Usage

```python
from django_safe_migrations import MigrationAnalyzer

analyzer = MigrationAnalyzer()

# Analyze all migrations
issues = analyzer.analyze_all()

# Analyze specific app
issues = analyzer.analyze_app('myapp')

# Analyze only new migrations
issues = analyzer.analyze_new_migrations()

for issue in issues:
    print(f"[{issue.rule_id}] {issue.message}")
    if issue.suggestion:
        print(f"Suggestion: {issue.suggestion}")
```

## 📚 Safe Migration Patterns

### Adding a NOT NULL Column

❌ **Unsafe:**

```python
migrations.AddField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255),  # NOT NULL, no default!
)
```

✅ **Safe:**

```python
# Migration 1: Add nullable field
migrations.AddField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, null=True),
)

# Migration 2: Backfill data (data migration)
def backfill_emails(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.filter(email__isnull=True).update(email='default@example.com')

migrations.RunPython(backfill_emails)

# Migration 3: Add NOT NULL constraint
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255),
)
```

### Creating an Index (PostgreSQL)

❌ **Unsafe:**

```python
migrations.AddIndex(
    model_name='user',
    index=models.Index(fields=['email'], name='user_email_idx'),
)
```

✅ **Safe:**

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Required!

    operations = [
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(fields=['email'], name='user_email_idx'),
        ),
    ]
```

## ⚠️ Known Limitations

### Static Analysis Only

Django Safe Migrations performs **static analysis** of migration files. It cannot:

- Know the actual size of your tables (all tables are treated equally)
- Detect issues that depend on runtime data (e.g., whether NULL values exist)
- Know your specific deployment strategy or downtime tolerance

**Recommendation**: Use suppression comments with explanations when you've verified a migration is safe for your specific situation.

### Database-Specific Rules

Some rules only apply to PostgreSQL:

| Rule  | PostgreSQL Only | Reason                                              |
| ----- | --------------- | --------------------------------------------------- |
| SM010 | Yes             | `CONCURRENTLY` is PostgreSQL-specific               |
| SM011 | Yes             | Concurrent unique indexes are PostgreSQL-specific   |
| SM012 | Yes             | Enum handling is PostgreSQL-specific                |
| SM018 | Yes             | `AddIndexConcurrently` is PostgreSQL-specific       |
| SM021 | Yes             | Concurrent unique constraint pattern                |
| SM030 | Yes             | `RemoveIndexConcurrently` is PostgreSQL-specific    |
| SM031 | Yes             | TEXT vs VARCHAR optimization is PostgreSQL-specific |
| SM034 | Yes             | IDENTITY columns are PostgreSQL-specific            |

For MySQL, SQLite, or other databases, these rules are automatically skipped.

### Cannot Detect All Unsafe Patterns

The analyzer may miss unsafe patterns in:

- Complex `RunSQL` statements (only basic pattern matching)
- Dynamic SQL generated at runtime
- Migrations that call external services
- Custom migration operations

### False Positives

Some detected issues may be false positives:

- **SM001** on new tables (no existing rows to worry about)
- **SM010** on small lookup tables (concurrent not needed)
- **SM020** when you've already backfilled NULL values

Use suppression comments to document why a pattern is safe in your case:

```python
# safe-migrations: ignore SM001 -- new table, no existing data
migrations.AddField(...)
```

### Source Inspection Limitations

Rules that inspect Python source code (like SM026 for RunPython batching) may not work in all environments:

- Compiled/optimized Python installations
- Some Docker configurations
- When source files are not available

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

```bash
# Clone the repo
git clone https://github.com/YasserShkeir/django-safe-migrations.git
cd django-safe-migrations

# Install dev dependencies
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest

# Run linters
make lint
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 💖 Support

If this project helps you ship safer migrations, consider supporting its development:

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-red.svg)](https://www.yasser-shkeir.com/donate)

## 🙏 Acknowledgments

Inspired by:

- [strong_migrations](https://github.com/ankane/strong_migrations) (Ruby)
- [django-pg-zero-downtime-migrations](https://github.com/tbicr/django-pg-zero-downtime-migrations)
- [squawk](https://github.com/sbdchd/squawk)
