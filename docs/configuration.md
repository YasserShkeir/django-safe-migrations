# Configuration

Django Safe Migrations can be configured through Django settings or command-line options.

## Django Settings

Add a `SAFE_MIGRATIONS` dictionary to your Django settings to customize behavior:

```python
# settings.py
SAFE_MIGRATIONS = {
    # Disable specific rules by ID
    "DISABLED_RULES": ["SM006", "SM008"],

    # Override severity levels for specific rules
    "RULE_SEVERITY": {
        "SM002": "INFO",  # Downgrade from WARNING to INFO
    },

    # Apps to exclude from checking (extends defaults)
    "EXCLUDED_APPS": [
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles",
        # Add your own apps to exclude:
        "django_celery_beat",
        "oauth2_provider",
    ],

    # Fail on warnings (same as --fail-on-warning)
    "FAIL_ON_WARNING": False,
}
```

### `DISABLED_RULES`

List of rule IDs to completely disable. Disabled rules won't be checked at all:

```python
SAFE_MIGRATIONS = {
    "DISABLED_RULES": [
        "SM006",  # Don't warn about column renames
        "SM008",  # Don't warn about data migrations
    ],
}
```

### `RULE_SEVERITY`

Override the severity level for specific rules. Valid values are `"ERROR"`, `"WARNING"`, and `"INFO"`:

```python
SAFE_MIGRATIONS = {
    "RULE_SEVERITY": {
        "SM002": "INFO",     # Downgrade drop column from WARNING to INFO
        "SM006": "WARNING",  # Upgrade rename column from INFO to WARNING
    },
}
```

### `EXCLUDED_APPS`

List of Django app labels to skip when checking migrations:

```python
SAFE_MIGRATIONS = {
    "EXCLUDED_APPS": [
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles",
        # Third-party apps you don't control:
        "django_celery_beat",
        "allauth",
    ],
}
```

### `FAIL_ON_WARNING`

If `True`, warnings will cause a non-zero exit code (same as `--fail-on-warning`):

```python
SAFE_MIGRATIONS = {
    "FAIL_ON_WARNING": True,
}
```

---

## Command Options

### `--format`

Choose the output format:

```bash
# Console output with colors (default)
python manage.py check_migrations --format=console

# JSON output for parsing
python manage.py check_migrations --format=json

# GitHub Actions annotations
python manage.py check_migrations --format=github
```

### `--fail-on-warning`

By default, only ERROR severity issues cause a non-zero exit code. Use this to also fail on warnings:

```bash
python manage.py check_migrations --fail-on-warning
```

### `--new-only`

Only check migrations that haven't been applied yet:

```bash
python manage.py check_migrations --new-only
```

This is useful in CI to only check new migrations in a PR.

### `--no-suggestions`

Hide the fix suggestions in output:

```bash
python manage.py check_migrations --no-suggestions
```

### `--exclude-apps`

Exclude specific apps from checking:

```bash
python manage.py check_migrations --exclude-apps legacy_app other_app
```

### `--include-django-apps`

By default, Django's built-in apps (auth, admin, etc.) are excluded. Include them with:

```bash
python manage.py check_migrations --include-django-apps
```

## Exit Codes

| Code | Meaning                                          |
| ---- | ------------------------------------------------ |
| 0    | No issues found (or only INFO)                   |
| 1    | ERROR found, or WARNING with `--fail-on-warning` |

## Programmatic Usage

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.rules.base import Severity

analyzer = MigrationAnalyzer()

# Analyze all migrations
issues = analyzer.analyze_all()

# Filter by severity
errors = [i for i in issues if i.severity == Severity.ERROR]
warnings = [i for i in issues if i.severity == Severity.WARNING]

# Get summary
summary = analyzer.get_summary(issues)
print(f"Total: {summary['total']}")
print(f"Errors: {summary['by_severity']['error']}")
```

## Custom Rules

You can provide your own rules:

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.rules.base import BaseRule, Issue, Severity

class MyCustomRule(BaseRule):
    rule_id = "CUSTOM001"
    severity = Severity.WARNING
    description = "My custom rule"

    def check(self, operation, migration, **kwargs):
        # Your logic here
        return None  # or return Issue(...)

# Use custom rules
analyzer = MigrationAnalyzer(rules=[MyCustomRule()])
issues = analyzer.analyze_all()
```

### `EXTRA_RULES` Configuration

You can register custom rules via Django settings using dotted import paths:

```python
# settings.py
SAFE_MIGRATIONS = {
    "EXTRA_RULES": [
        "myapp.migrations.rules.NoDropColumnRule",
        "myapp.migrations.rules.RequireReviewRule",
    ],
}
```

Each path must be a fully qualified dotted path to a class that extends `BaseRule`.

#### Security Considerations

> ⚠️ **Important:** The `EXTRA_RULES` setting uses dynamic imports via `importlib.import_module()`.

**Risk Assessment:**

| Aspect        | Status   | Notes                             |
| ------------- | -------- | --------------------------------- |
| Risk Level    | LOW      | Settings are developer-controlled |
| Attack Vector | None     | No user input reaches this code   |
| Mitigation    | Built-in | Only trusted code in settings.py  |

**Best Practices:**

1. **Only use trusted paths** - The import paths in `EXTRA_RULES` will be dynamically imported and executed. Only add paths to code you control.

2. **Review third-party rules** - If using rules from external packages, review the source code before adding them.

3. **Don't use user input** - Never construct `EXTRA_RULES` paths from user-supplied data:

   ```python
   # ❌ NEVER DO THIS
   SAFE_MIGRATIONS = {
       "EXTRA_RULES": [os.environ.get("CUSTOM_RULE")],  # Dangerous!
   }

   # ✅ SAFE - hardcoded paths only
   SAFE_MIGRATIONS = {
       "EXTRA_RULES": ["myapp.rules.MyRule"],
   }
   ```

4. **Validate in CI** - If you accept rule configurations in CI, validate paths against an allowlist:

   ```python
   ALLOWED_RULES = {
       "myapp.rules.StrictMode",
       "myapp.rules.RequireTests",
   }

   # Validate before use
   for rule_path in extra_rules:
       if rule_path not in ALLOWED_RULES:
           raise ValueError(f"Untrusted rule: {rule_path}")
   ```

**Why This is Safe:**

- Django settings files (`settings.py`) are Python code that runs with full privileges
- Any code in settings can already execute arbitrary Python
- `EXTRA_RULES` doesn't introduce new attack surface - it's equivalent to a regular `import` statement
- The setting is never exposed to end users or HTTP requests
