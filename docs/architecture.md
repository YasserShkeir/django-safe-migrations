# Architecture Overview

This document describes the high-level architecture of django-safe-migrations.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                 │
├─────────────────┬───────────────────────┬───────────────────────────┤
│   CLI Module    │  Management Command   │      Python API           │
│   (cli.py)      │ (check_migrations.py) │    (analyzer.py)          │
└────────┬────────┴───────────┬───────────┴─────────────┬─────────────┘
         │                    │                         │
         └────────────────────┼─────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MigrationAnalyzer                               │
│  - Loads migrations from Django's migration loader                   │
│  - Iterates through operations                                       │
│  - Applies rules to each operation                                   │
│  - Collects issues                                                   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Rule 1   │ │ Rule 2   │ │ Rule N   │
              │ (SM001)  │ │ (SM002)  │ │ (SMxxx)  │
              └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │            │            │
                   └────────────┼────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Issue Collection                             │
│  - Rule ID, severity, message                                        │
│  - File path, line number                                            │
│  - App label, migration name                                         │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Console  │ │  JSON    │ │  SARIF   │
              │ Reporter │ │ Reporter │ │ Reporter │
              └──────────┘ └──────────┘ └──────────┘
```

## Core Components

### Entry Points

#### CLI Module (`cli.py`)

Standalone command-line interface that can run without Django's manage.py:

```bash
python -m django_safe_migrations myapp --format=json
```

- Parses command-line arguments
- Configures Django settings
- Invokes MigrationAnalyzer
- Formats and outputs results

#### Management Command (`management/commands/check_migrations.py`)

Django management command integration:

```bash
python manage.py check_migrations myapp
```

- Integrates with Django's command framework
- Uses Django's output styling
- Supports all Django command options

#### Python API (`analyzer.py`)

Programmatic interface for custom tooling:

```python
from django_safe_migrations import MigrationAnalyzer

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()
```

### MigrationAnalyzer (`analyzer.py`)

The core analysis engine:

```python
class MigrationAnalyzer:
    def __init__(
        self,
        db_vendor: str = "postgresql",
        rules: list[BaseRule] | None = None,
        disabled_rules: set[str] | None = None,
        excluded_apps: set[str] | None = None,
    ):
        ...

    def analyze_all(self) -> list[Issue]:
        """Analyze all migrations in the project."""
        ...

    def analyze_app(self, app_label: str) -> list[Issue]:
        """Analyze migrations for a specific app."""
        ...

    def analyze_migration(self, migration) -> list[Issue]:
        """Analyze a single migration."""
        ...
```

**Responsibilities**:

1. Load migrations using Django's `MigrationLoader`
2. Filter apps based on configuration
3. Iterate through each migration's operations
4. Apply enabled rules to each operation
5. Check for suppression comments
6. Collect and return issues

### Rules System (`rules/`)

#### BaseRule (`rules/base.py`)

Abstract base class for all rules:

```python
class BaseRule(ABC):
    rule_id: str           # e.g., "SM001"
    severity: Severity     # ERROR, WARNING, INFO
    description: str       # Human-readable description
    db_vendors: list[str]  # Empty = all vendors

    @abstractmethod
    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs,
    ) -> Issue | None:
        """Check an operation for issues."""
        ...

    def get_suggestion(self, operation: Operation) -> str | None:
        """Return fix suggestion."""
        ...

    def applies_to_db(self, db_vendor: str) -> bool:
        """Check if rule applies to database."""
        ...

    def create_issue(self, operation, migration, message, **kwargs) -> Issue:
        """Helper to create Issue objects."""
        ...
```

#### Issue Dataclass (`rules/base.py`)

Represents a detected problem:

```python
@dataclass
class Issue:
    rule_id: str
    severity: Severity
    operation: str
    message: str
    suggestion: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    app_label: str | None = None
    migration_name: str | None = None
```

#### Rule Organization

Rules are organized by the operation type they check:

```
rules/
├── __init__.py        # Rule registry, get_all_rules()
├── base.py            # BaseRule, Issue, Severity
├── add_field.py       # SM001, SM022
├── remove_field.py    # SM002, SM003
├── alter_field.py     # SM004-SM006, SM013-SM014, SM020-SM021
├── run_sql.py         # SM007-SM008, SM012, SM016, SM024, SM026
├── add_index.py       # SM010-SM011, SM018
├── constraints.py     # SM009, SM015, SM017
├── naming.py          # SM019
├── relations.py       # SM023, SM025
└── graph.py           # SM027 (migration graph checks)
```

#### Rule Registry (`rules/__init__.py`)

Central registry for all rules:

```python
ALL_RULES: list[type[BaseRule]] = [
    NotNullWithoutDefaultRule,
    DropColumnUnsafeRule,
    # ... all built-in rules
]

def get_all_rules(db_vendor: str = "postgresql") -> list[BaseRule]:
    """Get all rules applicable to a database vendor."""
    ...

def get_all_rule_ids() -> set[str]:
    """Get all known rule IDs."""
    ...

def get_rule_by_id(rule_id: str) -> type[BaseRule] | None:
    """Look up a rule by ID."""
    ...
```

### Configuration (`conf.py`)

Handles settings from `settings.SAFE_MIGRATIONS`:

```python
def get_safe_migrations_settings() -> dict:
    """Get the SAFE_MIGRATIONS dict from Django settings."""
    ...

def get_disabled_rules() -> set[str]:
    """Get disabled rule IDs."""
    ...

def get_disabled_categories() -> set[str]:
    """Get disabled categories."""
    ...

def get_excluded_apps() -> set[str]:
    """Get excluded app labels."""
    ...

def get_extra_rules() -> list[str]:
    """Get custom rule import paths."""
    ...

def validate_config() -> list[str]:
    """Validate configuration and return warnings."""
    ...
```

### Reporters (`reporters.py`, `sarif_reporter.py`)

Format issues for output:

```python
class ConsoleReporter:
    """Human-readable terminal output with colors."""
    def report(self, issues: list[Issue]) -> str:
        ...

class JSONReporter:
    """Machine-readable JSON output."""
    def report(self, issues: list[Issue]) -> str:
        ...

class GitHubReporter:
    """GitHub Actions annotation format."""
    def report(self, issues: list[Issue]) -> str:
        ...

class SARIFReporter:
    """SARIF format for code scanning."""
    def report(self, issues: list[Issue]) -> str:
        ...
```

### Suppression System (`suppression.py`)

Handles inline suppression comments:

```python
def is_operation_suppressed(
    migration,
    operation,
    rule_id: str,
) -> bool:
    """Check if operation is suppressed for a rule."""
    ...

def parse_suppression_comment(comment: str) -> set[str]:
    """Parse rule IDs from suppression comment."""
    # Recognizes: # safe-migrations: ignore SM001, SM002
    ...
```

## Data Flow

### Analysis Flow

```
1. Entry Point (CLI/Command/API)
   │
   ▼
2. Load Configuration
   - Read SAFE_MIGRATIONS from settings
   - Validate configuration
   - Log warnings for invalid settings
   │
   ▼
3. Initialize Analyzer
   - Determine database vendor
   - Load applicable rules
   - Filter by disabled rules/categories
   - Load custom rules from EXTRA_RULES
   │
   ▼
4. Load Migrations
   - Use Django's MigrationLoader
   - Filter by app labels (if specified)
   - Exclude apps in EXCLUDED_APPS
   │
   ▼
5. Analyze Each Migration
   │
   ├─► For each operation:
   │   │
   │   ├─► Check suppression comments
   │   │   - Skip if suppressed
   │   │
   │   └─► Apply each rule:
   │       - rule.check(operation, migration)
   │       - Collect Issue if returned
   │
   ▼
6. Return Issues
   │
   ▼
7. Format Output
   - Select reporter based on --format
   - Generate output string
   │
   ▼
8. Exit
   - Exit code 1 if any ERROR severity
   - Exit code 0 otherwise
```

### Rule Execution Flow

```
rule.check(operation, migration, **kwargs)
   │
   ├─► Check operation type
   │   - Return None if not applicable
   │
   ├─► Inspect operation attributes
   │   - field type, options, etc.
   │
   ├─► Apply rule logic
   │   - Detect unsafe patterns
   │
   └─► Return Issue or None
       │
       └─► If Issue:
           - rule_id, severity from rule
           - message describing problem
           - suggestion for fix
           - file_path from migration
```

## Extension Points

### Custom Rules

Users can add custom rules via `EXTRA_RULES`:

```python
# settings.py
SAFE_MIGRATIONS = {
    "EXTRA_RULES": [
        "myapp.rules.MyCustomRule",
    ],
}

# myapp/rules.py
from django_safe_migrations.rules.base import BaseRule, Severity

class MyCustomRule(BaseRule):
    rule_id = "CUSTOM001"
    severity = Severity.WARNING
    description = "My custom rule"

    def check(self, operation, migration, **kwargs):
        # Custom logic
        ...
```

### Custom Reporters

Create custom output formats by implementing the reporter interface:

```python
class MyReporter:
    def report(self, issues: list[Issue]) -> str:
        # Format issues
        return formatted_string
```

## Threading Model

django-safe-migrations is **single-threaded**:

- Analysis runs sequentially through migrations
- No parallel rule execution
- Thread-safe for use in multi-threaded applications (no shared mutable state)

## Performance Characteristics

- **Memory**: O(n) where n = number of issues found
- **Time**: O(m × r) where m = migrations, r = rules
- **Startup**: ~100ms (Django initialization)
- **Per-migration**: ~1-5ms typical

## Dependencies

### Required

- Python 3.10+
- Django 4.2+

### Optional

- psycopg2/psycopg2-binary (PostgreSQL support)
- mysqlclient (MySQL support)

## File Structure

```
django_safe_migrations/
├── __init__.py              # Package exports, version
├── analyzer.py              # Core MigrationAnalyzer
├── cli.py                   # Standalone CLI
├── conf.py                  # Configuration handling
├── reporters.py             # Output formatters
├── sarif_reporter.py        # SARIF format support
├── suppression.py           # Inline suppression
├── management/
│   └── commands/
│       └── check_migrations.py  # Django command
└── rules/
    ├── __init__.py          # Rule registry
    ├── base.py              # BaseRule, Issue, Severity
    ├── add_field.py         # AddField rules
    ├── remove_field.py      # RemoveField rules
    ├── alter_field.py       # AlterField rules
    ├── run_sql.py           # RunSQL/RunPython rules
    ├── add_index.py         # Index rules
    ├── constraints.py       # Constraint rules
    ├── naming.py            # Naming convention rules
    ├── relations.py         # Relation rules
    └── graph.py             # Migration graph rules
```

## See Also

- [Custom Rules](custom-rules.md) - Writing custom rules
- [Configuration](configuration.md) - Configuration options
- [Contributing](../CONTRIBUTING.md) - Development guide
