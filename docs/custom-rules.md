# Custom Rules

Django Safe Migrations supports custom rules, allowing you to enforce migration policies specific to your project.

## Quick Start

1. Create a custom rule class:

```python
# myapp/migration_rules.py
from django_safe_migrations.rules.base import BaseRule, Issue, Severity

class RequireDescriptionRule(BaseRule):
    """Require all migrations to have a docstring."""

    rule_id = "MY001"
    severity = Severity.WARNING
    description = "Migration file should have a docstring describing the change"

    def check(self, operation, migration, **kwargs):
        # Check if migration module has a docstring
        module = migration.__module__
        import sys
        mod = sys.modules.get(module)
        if mod and not mod.__doc__:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message="Migration lacks a module-level docstring",
            )
        return None

    def get_suggestion(self, operation):
        return "Add a docstring at the top of the migration file describing the change."
```

2. Register the rule in settings:

```python
# settings.py
SAFE_MIGRATIONS = {
    "EXTRA_RULES": [
        "myapp.migration_rules.RequireDescriptionRule",
    ],
}
```

3. Run the checker:

```bash
python manage.py check_migrations
```

______________________________________________________________________

## BaseRule API

All custom rules must inherit from `BaseRule` and implement the required attributes and methods.

### Required Attributes

| Attribute     | Type       | Description                                  |
| ------------- | ---------- | -------------------------------------------- |
| `rule_id`     | `str`      | Unique identifier (e.g., `"MY001"`)          |
| `severity`    | `Severity` | Default severity: `ERROR`, `WARNING`, `INFO` |
| `description` | `str`      | Brief description shown in `--list-rules`    |

### Optional Attributes

| Attribute    | Type        | Default | Description                                         |
| ------------ | ----------- | ------- | --------------------------------------------------- |
| `db_vendors` | `list[str]` | `[]`    | Database vendors this rule applies to (empty = all) |

Example with database-specific rule:

```python
class PostgresOnlyRule(BaseRule):
    rule_id = "MY002"
    severity = Severity.ERROR
    description = "Checks PostgreSQL-specific migration patterns"
    db_vendors = ["postgresql"]  # Only runs on PostgreSQL
```

### Required Methods

#### `check(operation, migration, **kwargs) -> Issue | None`

The main method that inspects each migration operation.

**Parameters:**

- `operation` - A Django migration operation (e.g., `AddField`, `RunSQL`)
- `migration` - The migration object containing the operation
- `**kwargs` - Additional context:
  - `db_vendor`: Current database vendor string (e.g., `"postgresql"`)
  - `app_label`: The Django app label

**Returns:**

- An `Issue` object if a violation is found
- `None` if the operation is safe

**Example:**

```python
from django.db import migrations

class NoRawSQLRule(BaseRule):
    rule_id = "MY003"
    severity = Severity.ERROR
    description = "Disallow raw SQL migrations"

    def check(self, operation, migration, **kwargs):
        if isinstance(operation, migrations.RunSQL):
            return self.create_issue(
                operation=operation,
                migration=migration,
                message="Raw SQL migrations are not allowed in this project",
            )
        return None
```

### Optional Methods

#### `get_suggestion(operation) -> str | None`

Returns a fix suggestion for the issue.

```python
def get_suggestion(self, operation):
    return "Use Django ORM operations instead of RunSQL."
```

#### `applies_to_db(db_vendor) -> bool`

Override to customize database filtering logic. Default implementation checks `db_vendors` attribute.

```python
def applies_to_db(self, db_vendor):
    # Custom logic: apply to all except SQLite
    return db_vendor != "sqlite"
```

### Helper Method: `create_issue()`

Use `create_issue()` to generate properly formatted issues:

```python
return self.create_issue(
    operation=operation,
    migration=migration,
    message="Human-readable problem description",
    suggestion="Optional override for get_suggestion()",
    line_number=42,  # Optional: specific line number
)
```

This automatically populates:

- `rule_id` from the rule class
- `severity` from the rule class
- `file_path` from the migration
- `app_label` and `migration_name` from the migration

______________________________________________________________________

## Issue Dataclass

The `Issue` dataclass represents a detected problem:

```python
from django_safe_migrations.rules.base import Issue, Severity

issue = Issue(
    rule_id="MY001",
    severity=Severity.WARNING,
    operation="AddField('my_field')",
    message="Field name should follow naming convention",
    suggestion="Use snake_case for field names",
    file_path="myapp/migrations/0005_add_field.py",
    line_number=15,
    app_label="myapp",
    migration_name="0005_add_field",
)
```

### Fields

| Field            | Type          | Description                        |
| ---------------- | ------------- | ---------------------------------- |
| `rule_id`        | `str`         | Rule identifier                    |
| `severity`       | `Severity`    | Issue severity                     |
| `operation`      | `str`         | String representation of operation |
| `message`        | `str`         | Human-readable description         |
| `suggestion`     | `str \| None` | Fix suggestion                     |
| `file_path`      | `str \| None` | Path to migration file             |
| `line_number`    | `int \| None` | Line number in file                |
| `app_label`      | `str \| None` | Django app label                   |
| `migration_name` | `str \| None` | Migration name                     |

______________________________________________________________________

## Common Patterns

### Checking Operation Types

```python
from django.db import migrations

def check(self, operation, migration, **kwargs):
    # Check specific operation type
    if isinstance(operation, migrations.AddField):
        field = operation.field
        # Inspect field properties...

    # Check for any field modification
    if isinstance(operation, (migrations.AddField, migrations.AlterField)):
        # ...

    # Check for model operations
    if isinstance(operation, migrations.CreateModel):
        model_name = operation.name
        fields = operation.fields
        # ...
```

### Inspecting Field Properties

```python
from django.db import models

def check(self, operation, migration, **kwargs):
    if isinstance(operation, migrations.AddField):
        field = operation.field

        # Check field type
        if isinstance(field, models.TextField):
            # ...

        # Check field options
        if field.null is False and field.default is models.NOT_PROVIDED:
            return self.create_issue(...)

        # Check for specific attributes
        if hasattr(field, 'max_length') and field.max_length > 1000:
            return self.create_issue(...)
```

### Checking RunSQL Content

```python
import re

def check(self, operation, migration, **kwargs):
    if isinstance(operation, migrations.RunSQL):
        sql = operation.sql
        if isinstance(sql, str):
            # Pattern matching
            if re.search(r'DROP\s+TABLE', sql, re.IGNORECASE):
                return self.create_issue(...)

            # Check for reverse SQL
            if not operation.reverse_sql:
                return self.create_issue(...)
```

### Checking RunPython Functions

```python
import inspect

def check(self, operation, migration, **kwargs):
    if isinstance(operation, migrations.RunPython):
        func = operation.code

        # Get function source (if available)
        try:
            source = inspect.getsource(func)
            if '.all()' in source and '.iterator()' not in source:
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message="Data migration should use .iterator() for large tables",
                )
        except (OSError, TypeError):
            # Source not available (e.g., built-in or lambda)
            pass
```

### Database-Specific Rules

```python
class PostgresJsonRule(BaseRule):
    rule_id = "MY004"
    severity = Severity.INFO
    description = "Suggest using PostgreSQL JSONField"
    db_vendors = ["postgresql"]

    def check(self, operation, migration, **kwargs):
        db_vendor = kwargs.get("db_vendor", "")

        # Double-check database (belt and suspenders)
        if db_vendor != "postgresql":
            return None

        if isinstance(operation, migrations.AddField):
            if isinstance(operation.field, models.TextField):
                # Check if it looks like JSON storage
                if operation.name.endswith("_json") or operation.name.endswith("_data"):
                    return self.create_issue(
                        operation=operation,
                        migration=migration,
                        message=f"Consider using JSONField for '{operation.name}'",
                    )
        return None
```

______________________________________________________________________

## Testing Custom Rules

### Unit Testing

```python
import pytest
from django.db import migrations, models
from myapp.migration_rules import RequireDescriptionRule

class MockMigration:
    """Mock migration for testing."""
    app_label = "testapp"
    name = "0001_initial"
    __module__ = "testapp.migrations.0001_initial"

@pytest.fixture
def mock_migration():
    return MockMigration()

class TestRequireDescriptionRule:
    def test_detects_missing_docstring(self, mock_migration):
        rule = RequireDescriptionRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.EmailField(),
        )

        issue = rule.check(operation, mock_migration)

        # Depending on implementation, may or may not trigger
        # Adjust test based on your actual rule logic

    def test_allows_migration_with_docstring(self, mock_migration):
        # Setup mock with docstring
        rule = RequireDescriptionRule()
        # ...
```

### Integration Testing

```python
from io import StringIO
from django.core.management import call_command
from django.test import override_settings

@override_settings(SAFE_MIGRATIONS={
    "EXTRA_RULES": ["myapp.migration_rules.RequireDescriptionRule"],
})
def test_custom_rule_runs():
    """Test that custom rule is executed during check."""
    out = StringIO()
    call_command("check_migrations", "myapp", format="json", stdout=out)

    output = out.getvalue()
    # Parse and verify custom rule ran
```

______________________________________________________________________

## Best Practices

### Rule IDs

Use a consistent prefix for your custom rules to avoid conflicts:

```python
# Good - unique prefix
rule_id = "ACME001"  # Company prefix
rule_id = "PROJ001"  # Project prefix
rule_id = "MY001"    # Generic custom

# Avoid - conflicts with built-in rules
rule_id = "SM100"    # Reserved for django-safe-migrations
```

### Severity Guidelines

| Severity  | When to Use                                         |
| --------- | --------------------------------------------------- |
| `ERROR`   | Will definitely cause production issues             |
| `WARNING` | Might cause issues, or violates best practices      |
| `INFO`    | Informational, style preferences, or minor concerns |

### Performance

- Rules run for every operation in every migration
- Keep `check()` fast - avoid expensive operations
- Cache expensive computations if reused

```python
class ExpensiveRule(BaseRule):
    _cache = None

    def check(self, operation, migration, **kwargs):
        if self._cache is None:
            self._cache = self._expensive_setup()
        # Use cached data...
```

### Error Handling

Handle edge cases gracefully:

```python
def check(self, operation, migration, **kwargs):
    try:
        # Inspection that might fail
        source = inspect.getsource(operation.code)
    except (OSError, TypeError):
        # Skip if source unavailable
        return None

    # Continue with source analysis...
```

______________________________________________________________________

## Registering Rules

### Via Settings (Recommended)

```python
# settings.py
SAFE_MIGRATIONS = {
    "EXTRA_RULES": [
        "myapp.rules.Rule1",
        "myapp.rules.Rule2",
        "shared.migration_rules.CompanyRule",
    ],
}
```

### Programmatically

```python
from django_safe_migrations import MigrationAnalyzer
from myapp.rules import MyCustomRule

# Create analyzer with custom rules
analyzer = MigrationAnalyzer(rules=[MyCustomRule()])
issues = analyzer.analyze_all()
```

______________________________________________________________________

## Example: Complete Custom Rule

Here's a complete example of a custom rule that enforces a naming convention:

```python
# myapp/migration_rules.py
"""Custom migration rules for MyProject."""

from django.db import migrations, models
from django_safe_migrations.rules.base import BaseRule, Severity


class BooleanFieldNamingRule(BaseRule):
    """Enforce naming convention for boolean fields.

    Boolean fields should start with 'is_', 'has_', 'can_', or 'should_'.
    """

    rule_id = "MYPROJ001"
    severity = Severity.WARNING
    description = "Boolean fields should use is_/has_/can_/should_ prefix"

    ALLOWED_PREFIXES = ("is_", "has_", "can_", "should_", "allow_", "enable_")

    def check(self, operation, migration, **kwargs):
        # Only check AddField operations
        if not isinstance(operation, migrations.AddField):
            return None

        # Only check BooleanField and NullBooleanField
        field = operation.field
        if not isinstance(field, (models.BooleanField, models.NullBooleanField)):
            return None

        # Check naming convention
        field_name = operation.name
        if not field_name.startswith(self.ALLOWED_PREFIXES):
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"Boolean field '{field_name}' should start with "
                    f"one of: {', '.join(self.ALLOWED_PREFIXES)}"
                ),
            )

        return None

    def get_suggestion(self, operation):
        field_name = operation.name
        # Suggest a better name
        suggested = f"is_{field_name}"
        return f"Rename field to '{suggested}' or another prefix like 'has_', 'can_'"
```

______________________________________________________________________

## See Also

- [Configuration](configuration.md) - Full configuration reference
- [Rules Reference](rules.md) - Built-in rules documentation
- [API Reference](api.md) - Programmatic usage
