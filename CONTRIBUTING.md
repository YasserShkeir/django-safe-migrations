# Contributing to django-safe-migrations

Thank you for your interest in contributing to django-safe-migrations! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Docker (optional, for database tests)

### Development Setup

1. **Fork and clone the repository**:

   ```bash
   git clone https://github.com/YOUR_USERNAME/django-safe-migrations.git
   cd django-safe-migrations
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**:

   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**:

   ```bash
   pre-commit install
   ```

5. **Verify setup**:

   ```bash
   pytest tests/
   ```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Changes

- Write code following the style guidelines
- Add tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=django_safe_migrations

# Run specific test file
pytest tests/unit/rules/test_add_field_rules.py -v
```

### 4. Run Pre-commit Checks

```bash
pre-commit run --all-files
```

This runs:

- **black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting
- **mypy** - Type checking

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new rule for X"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub.

## Adding a New Rule

### 1. Choose a Rule ID

- Use the next available `SMxxx` number
- Check existing rules in `django_safe_migrations/rules/__init__.py`

### 2. Create the Rule Class

```python
# In appropriate file (e.g., rules/add_field.py)

class MyNewRule(BaseRule):
    """Detect [specific unsafe pattern].

    [Explanation of why this is unsafe]

    Safe pattern:
    [Description of how to do it safely]
    """

    rule_id = "SM0XX"
    severity = Severity.WARNING  # or ERROR, INFO
    description = "Short description for --list-rules"
    db_vendors = []  # Empty = all, or ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation has the unsafe pattern."""
        if not isinstance(operation, migrations.SomeOperation):
            return None

        # Detection logic here

        if unsafe_condition:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message="Clear description of the problem",
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for fixing the issue."""
        return """Multi-line suggestion with code examples..."""
```

### 3. Register the Rule

Add to `ALL_RULES` in `django_safe_migrations/rules/__init__.py`:

```python
from django_safe_migrations.rules.add_field import MyNewRule

ALL_RULES: list[type[BaseRule]] = [
    # ... existing rules ...
    MyNewRule,
]

__all__ = [
    # ... existing exports ...
    "MyNewRule",
]
```

### 4. Add Tests

Create tests in appropriate test file:

```python
# tests/unit/rules/test_add_field_rules.py

class TestMyNewRule:
    """Tests for MyNewRule (SM0XX)."""

    def test_detects_unsafe_pattern(self, mock_migration):
        """Test that rule detects the unsafe pattern."""
        rule = MyNewRule()
        operation = migrations.SomeOperation(...)

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM0XX"
        assert "expected text" in issue.message

    def test_allows_safe_pattern(self, mock_migration):
        """Test that rule allows safe patterns."""
        rule = MyNewRule()
        operation = migrations.SomeOperation(safe=True)

        issue = rule.check(operation, mock_migration)

        assert issue is None
```

### 5. Add Integration Test Migration

Create a test migration in `tests/test_project/testapp/migrations/`:

```python
# tests/test_project/testapp/migrations/00XX_test_my_rule.py
"""Migration to test SM0XX detection."""

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("testapp", "previous_migration")]

    operations = [
        # Operation that should trigger SM0XX
    ]
```

### 6. Update Documentation

- Add rule to `docs/rules.md`
- Update `CHANGELOG.md`

## Testing

### Unit Tests

Test individual components in isolation:

```bash
pytest tests/unit/ -v
```

### Integration Tests

Test the full analysis pipeline:

```bash
pytest tests/integration/ -v
```

### Database-Specific Tests

Run tests against PostgreSQL using Docker:

```bash
docker-compose -f docker-compose.test.yml up --build test-py313
```

Run all database backends:

```bash
docker-compose -f docker-compose.test.yml up --build test-all-dbs
```

### Coverage

Check test coverage:

```bash
pytest tests/ --cov=django_safe_migrations --cov-report=html
open htmlcov/index.html
```

## Code Style

### Python Style

- Follow PEP 8
- Use type hints for all public functions
- Maximum line length: 88 characters (black default)
- Use docstrings for classes and public methods

### Import Order

Imports are sorted by isort:

```python
# Standard library
import os
from typing import Optional

# Third-party
from django.db import migrations

# Local
from django_safe_migrations.rules.base import BaseRule
```

### Docstrings

Use Google-style docstrings:

```python
def function(param1: str, param2: int) -> bool:
    """Short description.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something is wrong.
    """
```

## Documentation

### Building Docs

Documentation is in Markdown in the `docs/` directory.

### Documentation Style

- Use clear, concise language
- Include code examples
- Keep examples up-to-date with the code

## Release Process

Releases are managed by maintainers. The process:

1. Update version in:

   - `pyproject.toml`
   - `django_safe_migrations/__init__.py`

2. Update `CHANGELOG.md`

3. Create a git tag:

   ```bash
   git tag -a v0.X.X -m "Release v0.X.X"
   git push origin v0.X.X
   ```

4. Build and upload to PyPI:

   ```bash
   python -m build
   twine upload dist/*
   ```

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/YasserShkeir/django-safe-migrations/discussions)
- **Bugs**: Open a [GitHub Issue](https://github.com/YasserShkeir/django-safe-migrations/issues)
- **Security**: Email security concerns privately (do not open public issues)

## Recognition

Contributors are recognized in:

- Git history
- Release notes for significant contributions
- README acknowledgments for major features

Thank you for contributing!
