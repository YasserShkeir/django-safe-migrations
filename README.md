# Django Safe Migrations

[![PyPI version](https://badge.fury.io/py/django-safe-migrations.svg)](https://badge.fury.io/py/django-safe-migrations)
[![Downloads](https://static.pepy.tech/badge/django-safe-migrations/month)](https://pepy.tech/project/django-safe-migrations)
[![CI](https://github.com/YasserShkeir/django-safe-migrations/actions/workflows/ci.yml/badge.svg)](https://github.com/YasserShkeir/django-safe-migrations/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YasserShkeir/django-safe-migrations/branch/main/graph/badge.svg)](https://codecov.io/gh/YasserShkeir/django-safe-migrations)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-safe-migrations.svg)](https://pypi.org/project/django-safe-migrations/)
[![Django Versions](https://img.shields.io/badge/django-3.2%20%7C%204.2%20%7C%205.0%20%7C%205.1%20%7C%206.0-blue.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Detect unsafe Django migrations before they break production.**

Django Safe Migrations analyzes your Django migrations and warns you about operations that could cause downtime, lock tables, or cause data loss in production environments.

## Features

- **Detect unsafe operations** before they reach production
- **PostgreSQL-aware** rules for concurrent index creation and more
- **Clear fix suggestions** with safe migration patterns
- **Multiple output formats**: Console (with colors), JSON, GitHub Actions annotations
- **Easy CI/CD integration** with GitHub Actions and pre-commit hooks
- **Configurable rules** to match your deployment strategy

## Rules

| Rule ID | Name                               | Severity | Description                                            |
| ------- | ---------------------------------- | -------- | ------------------------------------------------------ |
| SM001   | `not_null_without_default`         | ERROR    | Adding NOT NULL column without default will lock table |
| SM002   | `drop_column_unsafe`               | WARNING  | Dropping column while old code may reference it        |
| SM003   | `drop_table_unsafe`                | WARNING  | Dropping table while old code may reference it         |
| SM004   | `alter_column_type`                | WARNING  | Changing column type may rewrite table                 |
| SM005   | `add_foreign_key_validates`        | WARNING  | FK constraint validates existing rows (locks)          |
| SM006   | `rename_column`                    | INFO     | Column rename may break old code during deployment     |
| SM007   | `run_sql_unsafe`                   | WARNING  | RunSQL without reverse_sql is not reversible           |
| SM008   | `large_data_migration`             | INFO     | Data migration may be slow on large tables             |
| SM009   | `add_unique_constraint`            | ERROR    | Adding unique constraint requires full table scan      |
| SM010   | `index_not_concurrent`             | ERROR    | Index creation without CONCURRENTLY (PostgreSQL)       |
| SM011   | `unique_constraint_not_concurrent` | ERROR    | Unique constraint without concurrent index             |
| SM012   | `enum_add_value_transaction`       | ERROR    | Adding enum value inside transaction (PostgreSQL)      |
| SM013   | `alter_varchar_length`             | WARNING  | Decreasing VARCHAR length rewrites table               |
| SM014   | `rename_model`                     | WARNING  | Model rename may break FKs and external references     |
| SM015   | `alter_unique_together`            | WARNING  | Deprecated in favor of UniqueConstraint                |
| SM016   | `run_python_no_reverse`            | INFO     | RunPython without reverse_code is not reversible       |
| SM017   | `add_check_constraint`             | WARNING  | Check constraint validates all existing rows           |

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

| Option                  | Description                                |
| ----------------------- | ------------------------------------------ |
| `--format`              | Output format: `console`, `json`, `github` |
| `--fail-on-warning`     | Exit with error code on warnings           |
| `--new-only`            | Only check unapplied migrations            |
| `--no-suggestions`      | Hide fix suggestions                       |
| `--exclude-apps`        | Apps to exclude from checking              |
| `--include-django-apps` | Include Django's built-in apps             |

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

## � Support

If this project helps you ship safer migrations, consider supporting its development:

[![Sponsor](https://img.shields.io/badge/Sponsor-❤-red.svg)](https://www.yasser-shkeir.com/donate)

## �🙏 Acknowledgments

Inspired by:

- [strong_migrations](https://github.com/ankane/strong_migrations) (Ruby)
- [django-pg-zero-downtime-migrations](https://github.com/tbicr/django-pg-zero-downtime-migrations)
- [squawk](https://github.com/sbdchd/squawk)
