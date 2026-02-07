# Configuration

Django Safe Migrations can be configured through Django settings or command-line options.

## Django Settings

Add a `SAFE_MIGRATIONS` dictionary to your Django settings to customize behavior:

```python
# settings.py
SAFE_MIGRATIONS = {
    # Disable specific rules by ID
    "DISABLED_RULES": ["SM006", "SM008"],

    # Disable entire categories of rules
    "DISABLED_CATEGORIES": ["reversibility"],

    # Enable only specific categories (whitelist mode)
    # "ENABLED_CATEGORIES": ["destructive", "high-risk"],

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

    # Per-app rule configuration (v0.3.0+)
    "APP_RULES": {
        "legacy_app": {
            "DISABLED_RULES": ["SM001", "SM002"],  # Relax rules for legacy
        },
        "critical_app": {
            "ENABLED_CATEGORIES": ["high-risk"],  # Only check critical rules
        },
    },

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

### `DISABLED_CATEGORIES`

Disable entire categories of rules at once. Available categories:

| Category          | Description               | Rules                                           |
| ----------------- | ------------------------- | ----------------------------------------------- |
| `postgresql`      | PostgreSQL-specific rules | SM005, SM010, SM011, SM012, SM013, SM018        |
| `indexes`         | Index-related operations  | SM010, SM011, SM018                             |
| `constraints`     | Constraint operations     | SM009, SM011, SM015, SM017                      |
| `destructive`     | Destructive operations    | SM002, SM003, SM009                             |
| `locking`         | Table-locking operations  | SM004, SM005, SM010, SM011, SM013               |
| `data-loss`       | Potential data loss       | SM002, SM003, SM009                             |
| `reversibility`   | Non-reversible migrations | SM007, SM016, SM017                             |
| `data-migrations` | Data migration concerns   | SM007, SM008, SM016, SM017                      |
| `high-risk`       | High-risk operations      | SM001, SM002, SM003, SM010, SM011, SM018        |
| `informational`   | Info-level warnings       | SM006, SM014, SM019                             |
| `naming`          | Naming convention rules   | SM019                                           |
| `schema-changes`  | Schema modification rules | SM001, SM002, SM003, SM004, SM006, SM013, SM014 |

```python
SAFE_MIGRATIONS = {
    "DISABLED_CATEGORIES": [
        "reversibility",    # Don't check for reversible migrations
        "informational",    # Suppress info-level warnings
    ],
}
```

### `ENABLED_CATEGORIES`

When set, enables **whitelist mode** — only rules in the specified categories will run:

```python
SAFE_MIGRATIONS = {
    # Only check high-risk and destructive operations
    "ENABLED_CATEGORIES": ["high-risk", "destructive"],
}
```

!!! note
    If both `ENABLED_CATEGORIES` and `DISABLED_CATEGORIES` are set,
    `ENABLED_CATEGORIES` is applied first (whitelist), then
    `DISABLED_CATEGORIES` removes rules from that set.

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

### `APP_RULES`

Configure rules on a per-app basis. Each app can have its own `DISABLED_RULES`, `DISABLED_CATEGORIES`, `ENABLED_CATEGORIES`, and `RULE_SEVERITY`:

```python
SAFE_MIGRATIONS = {
    "APP_RULES": {
        # Legacy app with relaxed rules
        "legacy_app": {
            "DISABLED_RULES": ["SM001", "SM002"],
            "RULE_SEVERITY": {"SM004": "INFO"},
        },
        # Critical app with strict rules
        "payments": {
            "ENABLED_CATEGORIES": ["high-risk", "destructive"],
        },
        # Third-party integration with category disabled
        "webhooks": {
            "DISABLED_CATEGORIES": ["indexes"],
        },
    },
}
```

**Priority order** (highest to lowest):

1. App-specific `DISABLED_RULES`
2. App-specific `DISABLED_CATEGORIES` / `ENABLED_CATEGORIES`
3. Global `DISABLED_RULES`
4. Global `DISABLED_CATEGORIES` / `ENABLED_CATEGORIES`

This means you can have strict global rules but relax them for specific apps:

```python
SAFE_MIGRATIONS = {
    # Global: enable strict mode
    "ENABLED_CATEGORIES": ["high-risk"],

    "APP_RULES": {
        # But for legacy_app, allow everything
        "legacy_app": {
            "ENABLED_CATEGORIES": [],  # Empty = no category filtering
        },
    },
}
```

______________________________________________________________________

## Inline Suppression Comments

You can suppress specific rules on a per-operation basis using inline comments in your migration files.

### Syntax

```python
# safe-migrations: ignore SM001
# safe-migrations: ignore SM001, SM002
# safe-migrations: ignore SM001 -- reason for suppression
# safe-migrations: ignore all
```

### Usage

Place the suppression comment on the line immediately before the operation, or on the same line:

```python
operations = [
    # safe-migrations: ignore SM001 -- adding nullable first, will add NOT NULL later
    migrations.AddField(
        model_name='user',
        name='email',
        field=models.CharField(max_length=255, null=True),
    ),

    # safe-migrations: ignore SM002, SM003 -- intentional cleanup, field unused
    migrations.RemoveField(
        model_name='user',
        name='legacy_field',
    ),

    migrations.AddIndex(  # safe-migrations: ignore SM010 -- small table
        model_name='setting',
        index=models.Index(fields=['key'], name='setting_key_idx'),
    ),
]
```

### Ignore All Rules

To suppress all rules for an operation:

```python
# safe-migrations: ignore all -- this migration has been reviewed
migrations.RunSQL(
    sql='...',
    reverse_sql='...',
)
```

### Best Practices

1. **Always include a reason** — Future developers (including yourself) will want to know why:

   ```python
   # safe-migrations: ignore SM002 -- field removed from code in previous deploy
   ```

2. **Be specific** — Only suppress the rules that apply:

   ```python
   # ✅ Good - specific
   # safe-migrations: ignore SM001

   # ❌ Avoid - too broad
   # safe-migrations: ignore all
   ```

3. **Keep suppressions minimal** — If you're suppressing many rules, consider if the migration is actually safe.

4. **Document in PR** — When adding suppressions, explain in your PR description why it's safe.

______________________________________________________________________

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

# GitLab Code Quality format
python manage.py check_migrations --format=gitlab

# SARIF for GitHub Code Scanning
python manage.py check_migrations --format=sarif
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

### `--diff`

Only check migrations that have changed since a base branch:

```bash
# Diff against main (default)
python manage.py check_migrations --diff

# Diff against a specific branch
python manage.py check_migrations --diff develop
```

### `--baseline`

Exclude issues that are present in a baseline file:

```bash
python manage.py check_migrations --baseline .migration-baseline.json
```

### `--generate-baseline`

Generate a baseline file from current issues and exit:

```bash
python manage.py check_migrations --generate-baseline .migration-baseline.json
```

This is useful for adopting django-safe-migrations incrementally on an existing project.

### `--interactive`

Interactively review each issue with options to keep, skip, show fix, or quit:

```bash
python manage.py check_migrations --interactive
```

### `--verbose`

Show progress information during analysis:

```bash
python manage.py check_migrations --verbose
```

### `--watch`

Watch migration files for changes and re-run analysis automatically:

```bash
python manage.py check_migrations --watch
```

Requires the `watchdog` package: `pip install django-safe-migrations[watch]`

### `--list-rules`

List all available rules and exit:

```bash
python manage.py check_migrations --list-rules
python manage.py check_migrations --list-rules --format=json
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
