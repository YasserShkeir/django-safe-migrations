# Django Compatibility

Django Safe Migrations supports a wide range of Django and Python versions. This page documents version compatibility, known API differences we handle, and how we test across versions.

## Supported Versions

### Version Matrix

| Python | Django 3.2 | Django 4.2 | Django 5.0 | Django 5.1 | Django 6.0 |
| ------ | ---------- | ---------- | ---------- | ---------- | ---------- |
| 3.9    | Yes        | Yes        | No         | No         | No         |
| 3.10   | Yes        | Yes        | Yes        | Yes        | No         |
| 3.11   | Yes        | Yes        | Yes        | Yes        | Yes        |
| 3.12   | Yes        | Yes        | Yes        | Yes        | Yes        |
| 3.13   | No         | Yes        | Yes        | Yes        | Yes        |

**Notes:**

- Django 3.2 is the minimum supported version (LTS)
- Django 5.0+ requires Python 3.10+
- Django 6.0+ requires Python 3.11+
- Python 3.9 support will be dropped when Django 3.2 reaches end-of-life

### Official Support Policy

We follow Django's [supported versions policy](https://www.djangoproject.com/download/#supported-versions):

- All current LTS releases (Django 3.2, 4.2)
- All current feature releases (Django 5.x, 6.x)
- We test against the latest patch version of each minor release

## Known API Changes

Django's internal APIs change between versions. We handle these automatically so your migration checks work regardless of Django version.

### CheckConstraint API (Django 5.1+)

**The Change:**

| Django Version | Parameter Name | Status               |
| -------------- | -------------- | -------------------- |
| < 5.1          | `check=`       | Required             |
| 5.1            | `check=`       | Deprecated (warning) |
| 5.1            | `condition=`   | New, preferred       |
| 6.0+           | `check=`       | Removed              |
| 6.0+           | `condition=`   | Required             |

**How We Handle It:**

Our test suite uses version-aware fixtures to create `CheckConstraint` instances:

```python
import django
from django.db import models

def create_check_constraint(condition, name):
    """Create a CheckConstraint compatible with any Django version."""
    if django.VERSION >= (5, 1):
        return models.CheckConstraint(condition=condition, name=name)
    else:
        return models.CheckConstraint(check=condition, name=name)
```

**Impact on Users:**

None. The SM017 rule correctly detects `AddConstraint` operations with `CheckConstraint` regardless of which parameter was used.

### Index Creation Introspection

Django's index introspection changed in Django 4.1:

- **Django < 4.1:** Limited index metadata
- **Django 4.1+:** Enhanced `Index` and `UniqueConstraint` introspection

Our SM010 and SM011 rules work with both APIs by checking the operation type rather than introspecting database state.

### `NOT_PROVIDED` Sentinel

The location of Django's `NOT_PROVIDED` sentinel varies:

```python
# Django 3.2 - 4.x
from django.db.models.fields import NOT_PROVIDED

# Django 5.x+
from django.db.models import NOT_PROVIDED
```

We handle this with a version-agnostic import in our SM001 rule.

## How We Test

### Automated CI Matrix

Every pull request runs tests against our full version matrix using GitHub Actions:

```yaml
strategy:
  matrix:
    python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
    django-version: ["3.2", "4.2", "5.0", "5.1", "6.0"]
    exclude:
      # Django 5.0+ requires Python 3.10+
      - python-version: "3.9"
        django-version: "5.0"
      - python-version: "3.9"
        django-version: "5.1"
      - python-version: "3.9"
        django-version: "6.0"
      # Django 6.0 requires Python 3.11+
      - python-version: "3.10"
        django-version: "6.0"
      # Python 3.13 not supported on Django 3.2
      - python-version: "3.13"
        django-version: "3.2"
```

### Docker Multi-Database Testing

For database-specific rules (PostgreSQL, MySQL), we use Docker Compose:

```bash
docker-compose -f docker-compose.test.yml up test-py311 --build
```

This runs tests against:

- PostgreSQL 15
- MySQL 8.0
- SQLite (default)

### Local Testing

To test against a specific Django version locally:

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install specific Django version
pip install "Django>=5.1,<5.2"

# Install package in dev mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Writing Compatible Code

When contributing to django-safe-migrations, follow these patterns:

### Version Checks

```python
import django

if django.VERSION >= (5, 1):
    # Django 5.1+ code path
    pass
else:
    # Legacy code path
    pass
```

### Import Guards

```python
try:
    from django.db.models import NOT_PROVIDED
except ImportError:
    from django.db.models.fields import NOT_PROVIDED
```

### Type Hints with Compatibility

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db import migrations
```

## Reporting Compatibility Issues

If you encounter a compatibility issue:

1. **Check the version:** Run `python -c "import django; print(django.VERSION)"`

2. **Reproduce with minimal case:** Create a small migration that triggers the issue

3. **Open an issue:** Include:

   - Python version
   - Django version
   - Full error traceback
   - Migration code (if possible)

4. **Link to Django release notes:** If the issue relates to a Django API change, include a link to the relevant release notes

[Open an issue on GitHub](https://github.com/YasserShkeir/django-safe-migrations/issues/new?labels=compatibility&template=compatibility_issue.md)

## Deprecation Policy

When Django deprecates an API we use:

1. **Immediate:** We add support for the new API
2. **Same release:** We keep backward compatibility with the old API
3. **When Django removes it:** We remove our backward compatibility code

This ensures you can upgrade Django versions without upgrading django-safe-migrations simultaneously (and vice versa).

## Database Compatibility

While django-safe-migrations performs static analysis (no database connection required), some rules are database-specific:

| Rule       | PostgreSQL | MySQL | SQLite | Other |
| ---------- | ---------- | ----- | ------ | ----- |
| SM010      | Yes        | No    | No     | No    |
| SM011      | Yes        | No    | No     | No    |
| SM012      | Yes        | No    | No     | No    |
| All others | Yes        | Yes   | Yes    | Yes   |

Database-specific rules use the `db_vendors` attribute:

```python
class NonConcurrentIndexRule(BaseRule):
    rule_id = "SM010"
    db_vendors = ["postgresql"]  # Only applies to PostgreSQL
```

When analyzing migrations, pass the database vendor to enable/disable these rules:

```bash
# Assume PostgreSQL (enables all PostgreSQL-specific rules)
python manage.py check_migrations

# The tool auto-detects your default database from settings
```
