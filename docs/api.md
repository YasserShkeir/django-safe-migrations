# API Reference

This page documents the public Python API for `django-safe-migrations`.

## MigrationAnalyzer

::: django_safe_migrations.analyzer.MigrationAnalyzer
options:
show_root_heading: true
show_source: false
members:
\- __init__
\- analyze_migration
\- analyze_app
\- analyze_all
\- analyze_new_migrations
\- get_summary

### Basic Usage

```python
from django_safe_migrations import MigrationAnalyzer

# Create analyzer
analyzer = MigrationAnalyzer()

# Analyze all migrations
issues = analyzer.analyze_all()

# Analyze specific app
issues = analyzer.analyze_app('myapp')

# Analyze only unapplied migrations
issues = analyzer.analyze_new_migrations()

# Get summary
summary = analyzer.get_summary(issues)
print(f"Found {summary['total']} issues")
print(f"Errors: {summary['by_severity']['error']}")
print(f"Warnings: {summary['by_severity']['warning']}")
```

### Custom Configuration

```python
from django_safe_migrations import MigrationAnalyzer

# Disable specific rules
analyzer = MigrationAnalyzer(disabled_rules=["SM006", "SM008"])

# Target specific database
analyzer = MigrationAnalyzer(db_vendor="postgresql")

# Use custom rules
from django_safe_migrations.rules import get_all_rules

custom_rules = [r for r in get_all_rules() if r.rule_id.startswith("SM01")]
analyzer = MigrationAnalyzer(rules=custom_rules)
```

## Issue

::: django_safe_migrations.rules.base.Issue
options:
show_root_heading: true
show_source: false

### Working with Issues

```python
from django_safe_migrations import MigrationAnalyzer, Severity

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()

for issue in issues:
    # Access issue properties
    print(f"Rule: {issue.rule_id}")
    print(f"Severity: {issue.severity.value}")
    print(f"Message: {issue.message}")
    print(f"File: {issue.file_path}:{issue.line_number}")
    print(f"Suggestion: {issue.suggestion}")
    print()

    # Convert to dict (for JSON serialization)
    issue_dict = issue.to_dict()

# Filter by severity
errors = [i for i in issues if i.severity == Severity.ERROR]
warnings = [i for i in issues if i.severity == Severity.WARNING]
```

## Severity

::: django_safe_migrations.rules.base.Severity
options:
show_root_heading: true
show_source: false

### Severity Levels

| Level     | Value       | Description                   |
| --------- | ----------- | ----------------------------- |
| `ERROR`   | `"error"`   | Will likely break production  |
| `WARNING` | `"warning"` | Might cause issues under load |
| `INFO`    | `"info"`    | Best practice recommendation  |

```python
from django_safe_migrations import Severity

# Compare severities
if issue.severity == Severity.ERROR:
    print("Critical issue!")

# Get string value
print(issue.severity.value)  # "error", "warning", or "info"
```

## Reporters

### ConsoleReporter

Outputs colorized, human-readable reports to the terminal.

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.reporters import ConsoleReporter

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()

reporter = ConsoleReporter(show_suggestions=True)
reporter.report(issues)
```

### JsonReporter

Outputs machine-readable JSON for CI/CD pipelines.

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.reporters import JsonReporter

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()

reporter = JsonReporter()
reporter.report(issues)  # Prints JSON to stdout
```

Output format:

```json
{
  "issues": [
    {
      "rule_id": "SM001",
      "severity": "error",
      "operation": "AddField(user.email)",
      "message": "Adding NOT NULL field 'email' without a default",
      "suggestion": "Add as nullable first, backfill, then add NOT NULL",
      "file_path": "myapp/migrations/0002_add_email.py",
      "line_number": 15,
      "app_label": "myapp",
      "migration_name": "0002_add_email"
    }
  ],
  "summary": {
    "total": 1,
    "errors": 1,
    "warnings": 0,
    "info": 0
  }
}
```

### GithubReporter

Outputs GitHub Actions workflow commands for inline PR annotations.

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.reporters import GithubReporter

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()

reporter = GithubReporter()
reporter.report(issues)
```

Output format:

```
::error file=myapp/migrations/0002_add_email.py,line=15::[SM001] Adding NOT NULL field 'email' without a default
```

### Using get_reporter()

```python
from django_safe_migrations.reporters import get_reporter

# Get reporter by name
reporter = get_reporter("console", show_suggestions=True)
reporter = get_reporter("json")
reporter = get_reporter("github")
```

## Creating Custom Rules

You can create custom rules by extending `BaseRule`:

```python
from typing import Optional
from django.db import migrations
from django_safe_migrations.rules.base import BaseRule, Issue, Severity


class NoRawSqlRule(BaseRule):
    """Detect raw SQL that might be dangerous."""

    rule_id = "CUSTOM001"
    severity = Severity.WARNING
    description = "Raw SQL detected in migration"

    def check(self, operation, migration, **kwargs) -> Optional[Issue]:
        if not isinstance(operation, migrations.RunSQL):
            return None

        sql = operation.sql if isinstance(operation.sql, str) else str(operation.sql)

        # Check for dangerous patterns
        dangerous = ["DROP", "TRUNCATE", "DELETE FROM"]
        for pattern in dangerous:
            if pattern in sql.upper():
                return self.create_issue(
                    operation=operation,
                    message=f"Dangerous SQL pattern detected: {pattern}",
                    migration=migration,
                )

        return None

    def get_suggestion(self, operation) -> str:
        return "Review this SQL carefully and add reverse_sql for safety."


# Use custom rule
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.rules import get_all_rules

rules = get_all_rules() + [NoRawSqlRule()]
analyzer = MigrationAnalyzer(rules=rules)
```

## Module Exports

The main module exports these public classes:

```python
from django_safe_migrations import (
    MigrationAnalyzer,  # Main analyzer class
    Issue,              # Issue dataclass
    Severity,           # Severity enum
    __version__,        # Package version string
)
```
