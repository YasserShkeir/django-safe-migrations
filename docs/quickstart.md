# Quick Start

This guide will get you up and running with Django Safe Migrations in 5 minutes.

## Step 1: Install

```bash
pip install django-safe-migrations
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_safe_migrations',
]
```

## Step 2: Check Your Migrations

Run the check command:

```bash
python manage.py check_migrations
```

If you have any unsafe migrations, you'll see output like:

```
Found 1 migration issue(s):

✖ ERROR [SM001] myapp/migrations/0002_add_email.py:15
   Adding NOT NULL field 'email' to 'user' without a default value will lock the table

   💡 Suggestion:
      Safe pattern for adding NOT NULL field:
      1. Add field as nullable
      2. Backfill existing rows in batches
      3. Add NOT NULL constraint in separate migration
```

## Step 3: Fix the Issue

Follow the suggestion to fix your migration:

### Before (Unsafe)

```python
# 0002_add_email.py
migrations.AddField(
    model_name='user',
    name='email',
    field=models.EmailField(),  # NOT NULL, no default!
)
```

### After (Safe)

```python
# 0002_add_email_nullable.py
migrations.AddField(
    model_name='user',
    name='email',
    field=models.EmailField(null=True),  # Nullable first
)

# 0003_backfill_email.py
def backfill_emails(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    # For large tables, use batching (see Rules reference for SM001)
    User.objects.filter(email__isnull=True).update(email='unknown@example.com')

migrations.RunPython(backfill_emails, migrations.RunPython.noop)

# 0004_email_not_null.py
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.EmailField(),  # Now safe to add NOT NULL
)
```

## Step 4: Add to CI

Add to your GitHub Actions workflow:

```yaml
# .github/workflows/migrations.yml
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
      - run: pip install django-safe-migrations Django
      - run: python manage.py check_migrations --format=github
```

### More Options

```bash
# Only check migrations changed since main
python manage.py check_migrations --diff

# Generate a baseline for existing issues
python manage.py check_migrations --generate-baseline .migration-baseline.json

# Run with baseline to catch only new issues
python manage.py check_migrations --baseline .migration-baseline.json

# Interactively review each issue
python manage.py check_migrations --interactive

# Watch for changes during development
pip install django-safe-migrations[watch]
python manage.py check_migrations --watch
```

## Next Steps

- Read about all [Rules](rules.md)
- Learn [Safe Patterns](patterns.md) for common operations
- Set up [Pre-commit Hooks](pre-commit.md)
