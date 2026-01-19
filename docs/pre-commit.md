# Pre-commit Integration

[pre-commit](https://pre-commit.com/) is a framework for managing git hooks. With `django-safe-migrations` integrated into pre-commit, unsafe migrations are detected before they're even committed.

## Quick Setup

### Option 1: Local Hook (Recommended)

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations --new-only
        language: system
        types: [python]
        files: migrations/
        pass_filenames: false
```

This approach uses your existing Django project setup directly.

### Option 2: Remote Hook

You can also use the hook directly from the repository:

```yaml
repos:
  - repo: https://github.com/YasserShkeir/django-safe-migrations
    rev: v0.2.0  # Use the latest version
    hooks:
      - id: check-migrations
```

!!! note
    The remote hook requires `DJANGO_SETTINGS_MODULE` to be set in your environment.

## Configuration Options

### Fail on Warnings

To block commits that have warnings (not just errors):

```yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations --new-only --fail-on-warning
        language: system
        types: [python]
        files: migrations/
        pass_filenames: false
```

### Exclude Specific Apps

To skip checking certain apps:

```yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations --new-only --exclude-apps legacy_app old_app
        language: system
        types: [python]
        files: migrations/
        pass_filenames: false
```

### Check All Migrations

To check all migrations (not just unapplied ones):

```yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations
        language: system
        types: [python]
        files: migrations/
        pass_filenames: false
```

## Installation

1. Install pre-commit if you haven't already:

```bash
pip install pre-commit
```

2. Create `.pre-commit-config.yaml` in your project root with one of the configurations above.

3. Install the hooks:

```bash
pre-commit install
```

4. (Optional) Run against all files to check existing migrations:

```bash
pre-commit run --all-files
```

## How It Works

When you run `git commit`, pre-commit will:

1. Detect if any migration files are staged
2. Run `check_migrations` on those files
3. Block the commit if unsafe operations are found
4. Show suggestions for fixing the issues

## Example Output

```
Check Django migrations................................................Failed
- hook id: check-migrations
- exit code: 1

Found 1 migration issue(s):

✖ ERROR [SM001] myapp/migrations/0002_add_field.py
   Adding NOT NULL field 'email' without a default value

   💡 Suggestion:
      Add the field as nullable first, then backfill, then add NOT NULL.
```

## Skipping Checks

If you need to bypass the check for a specific commit:

```bash
git commit --no-verify -m "Emergency fix"
```

!!! warning
    Use `--no-verify` sparingly. It's better to fix the migration issue or configure rule suppression.

## Combining with Other Hooks

A complete `.pre-commit-config.yaml` might look like:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black

  - repo: local
    hooks:
      - id: check-migrations
        name: Check Django migrations
        entry: python manage.py check_migrations --new-only --fail-on-warning
        language: system
        types: [python]
        files: migrations/
        pass_filenames: false
```

## Troubleshooting

### "Django not configured" Error

If you see this error, ensure:

1. Your virtual environment is activated
2. `DJANGO_SETTINGS_MODULE` is set, or
3. You're using the local hook approach with `language: system`

### Hook Not Running

Ensure:

1. The hook is installed: `pre-commit install`
2. Your staged files match the `files` pattern (e.g., `migrations/`)
3. The file type is `python`

### Slow Hook Execution

Use `--new-only` to only check unapplied migrations:

```yaml
entry: python manage.py check_migrations --new-only
```

This significantly speeds up the check by skipping already-applied migrations.
