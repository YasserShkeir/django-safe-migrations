# Testing Strategy for django-safe-migrations

This document provides a comprehensive overview of the testing strategy for `django-safe-migrations`,
covering matrix testing, Docker integration, multi-database backend testing, and CI/CD best practices.

## Table of Contents

1. [Overview](#overview)
2. [Test Matrix](#test-matrix)
3. [Running Tests Locally](#running-tests-locally)
4. [Pre-commit Hooks](#pre-commit-hooks)
5. [Docker Testing](#docker-testing)
6. [Multi-Database Backend Testing](#multi-database-backend-testing)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Coverage Requirements](#coverage-requirements)
9. [Adding New Tests](#adding-new-tests)

______________________________________________________________________

## Overview

The testing strategy is designed to ensure `django-safe-migrations` works correctly across:

- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Django versions**: 3.2, 4.2, 5.0, 5.1, 6.0
- **Database backends**: SQLite, PostgreSQL, MySQL/MariaDB
- **Operating systems**: Linux (Ubuntu), macOS, Windows

### Test Types

| Type              | Purpose                                 | Location             | Run Frequency |
| ----------------- | --------------------------------------- | -------------------- | ------------- |
| Unit Tests        | Test individual components in isolation | `tests/unit/`        | Every commit  |
| Integration Tests | Test components working together        | `tests/integration/` | Every commit  |

Database-specific behavior is covered within `tests/unit/` and `tests/integration/`,
gated by the `@pytest.mark.postgres` and `@pytest.mark.mysql` markers.

______________________________________________________________________

## Test Matrix

### Python × Django Compatibility Matrix

```
             │ Django 3.2 │ Django 4.2 │ Django 5.0 │ Django 5.1 │ Django 6.0 │
─────────────┼────────────┼────────────┼────────────┼────────────┼────────────┤
Python 3.9   │    Yes     │    Yes     │     No     │     No     │     No     │
Python 3.10  │    Yes     │    Yes     │    Yes     │    Yes     │     No     │
Python 3.11  │    Yes     │    Yes     │    Yes     │    Yes     │     No     │
Python 3.12  │     No     │    Yes     │    Yes     │    Yes     │    Yes     │
Python 3.13  │     No     │    Yes     │    Yes     │    Yes     │    Yes     │
Python 3.14  │     No     │     No     │     No     │     No     │    Yes     │
```

**Note**: Django 5.0+ requires Python 3.10+; Django 6.0 requires Python 3.12+;
Django 3.2 doesn't support Python 3.12+; Python 3.14 is only tested with Django 6.0.

### Using Tox for Matrix Testing

```bash
# Run all environments
tox

# Run specific environment
tox -e py311-django42

# Run specific Python version with all Django versions
tox -e py311

# List all available environments
tox --listenvs
```

### tox.ini Configuration

```ini
[tox]
isolated_build = True
envlist =
    py39-django{32,42}
    py310-django{32,42,50,51}
    py311-django{42,50,51}
    py312-django{42,50,51,60}
    py313-django{42,50,51,60}
    lint
    typecheck

[testenv]
deps =
    django32: Django>=3.2,<4.0
    django42: Django>=4.2,<5.0
    django50: Django>=5.0,<5.1
    django51: Django>=5.1,<5.2
    django60: Django>=6.0,<6.1
    pytest>=7.0
    pytest-django>=4.5
    pytest-cov>=4.0
    pytest-xdist>=3.0
commands =
    pytest tests -n 2 -q --cov=django_safe_migrations --cov-report=term-missing {posargs}

[testenv:lint]
skip_install = true
deps =
    black>=22.0
    flake8>=5.0
    isort>=5.0
commands =
    black --check django_safe_migrations tests
    isort --check-only django_safe_migrations tests
    flake8 django_safe_migrations tests

[testenv:typecheck]
deps =
    mypy>=1.0
    django-stubs>=4.0
    Django>=4.2
commands =
    mypy django_safe_migrations
```

See the actual `tox.ini` in the repository for the full configuration.

______________________________________________________________________

## Running Tests Locally

### Prerequisites

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Basic Test Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/rules/test_add_field_rules.py

# Run specific test class
pytest tests/unit/rules/test_add_field_rules.py::TestNotNullWithoutDefaultRule

# Run specific test
pytest tests/unit/rules/test_add_field_rules.py::TestNotNullWithoutDefaultRule::test_detects_not_null_without_default

# Run with coverage
pytest --cov=django_safe_migrations --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Stop on first failure
pytest -x
```

### Using Make Commands

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run linting
make lint

# Run type checking
make typecheck

# Run all CI checks (lint, typecheck, test)
make ci-check
```

______________________________________________________________________

## Pre-commit Hooks

Pre-commit hooks run automatically before each commit to ensure code quality.

### Installation

```bash
pip install pre-commit
pre-commit install
```

### Manual Run

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run mypy --all-files
```

### Configured Hooks

| Hook                  | Purpose                       | Configuration    |
| --------------------- | ----------------------------- | ---------------- |
| `trailing-whitespace` | Remove trailing whitespace    | Auto-fix         |
| `end-of-file-fixer`   | Ensure files end with newline | Auto-fix         |
| `check-yaml`          | Validate YAML syntax          | -                |
| `debug-statements`    | Detect debugger imports       | Error            |
| `black`               | Code formatting               | `pyproject.toml` |
| `isort`               | Import sorting                | `pyproject.toml` |
| `flake8`              | Linting                       | `.flake8`        |
| `mypy`                | Type checking                 | `pyproject.toml` |
| `bandit`              | Security scanning             | -                |

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements

  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        additional_dependencies:
          - flake8-docstrings

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies:
          - django-stubs>=4.0

  - repo: https://github.com/pycqa/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
```

______________________________________________________________________

## Docker Testing

Docker enables consistent testing across environments and database backends.

### Docker Compose Setup

Create `docker-compose.test.yml`:

```yaml
version: "3.9"

services:
  # PostgreSQL Database (exposed on host port 15432)
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "15432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  # MySQL Database (exposed on host port 13306)
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: test_db
      MYSQL_USER: test_user
      MYSQL_PASSWORD: test_password
      MYSQL_ROOT_PASSWORD: root_password
    ports:
      - "13306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Test runner - Python 3.11 (representative; the real file also defines
  # test-py310, test-py312, test-py313, test-py314, test-mysql, and test-all-dbs)
  test-py311:
    build:
      context: .
      dockerfile: Dockerfile.test
      args:
        PYTHON_VERSION: "3.11"
    depends_on:
      postgres:
        condition: service_healthy
      mysql:
        condition: service_healthy
    environment:
      - DJANGO_SETTINGS_MODULE=tests.settings.postgres
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=test_db
      - POSTGRES_USER=test_user
      - POSTGRES_PASSWORD=test_password
    volumes:
      - .:/app
    command: pytest -v --cov=django_safe_migrations
```

See the actual `docker-compose.test.yml` in the repository for the full configuration.

### Dockerfile.test

```dockerfile
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code first
COPY . .

# Install Python dependencies including the package itself and database drivers
RUN pip install --no-cache-dir -e ".[dev,postgres,mysql]"

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Run tests by default
CMD ["pytest", "-v"]
```

### Running Docker Tests

```bash
# Run all tests with all databases
docker compose -f docker-compose.test.yml up --build

# Run specific Python version
docker compose -f docker-compose.test.yml up test-py312 --build

# Run with specific database only
docker compose -f docker-compose.test.yml up postgres test-py311 --build

# Clean up
docker compose -f docker-compose.test.yml down -v
```

______________________________________________________________________

## Multi-Database Backend Testing

### Database-Specific Rules

Some rules only apply to specific databases:

| Rule                        | SQLite | PostgreSQL | MySQL |
| --------------------------- | ------ | ---------- | ----- |
| SM001 (NOT NULL)            | Yes    | Yes        | Yes   |
| SM002 (Drop Column)         | Yes    | Yes        | Yes   |
| SM003 (Drop Table)          | Yes    | Yes        | Yes   |
| SM010 (Index CONCURRENTLY)  | No     | Yes        | No    |
| SM011 (Unique CONCURRENTLY) | No     | Yes        | No    |

### Test Settings per Database

Create `tests/settings/` with database-specific settings:

**tests/settings/sqlite.py:**

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
```

**tests/settings/postgres.py:**

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "test_db"),
        "USER": os.environ.get("POSTGRES_USER", "test_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "test_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
```

**tests/settings/mysql.py:**

```python
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DB", "test_db"),
        "USER": os.environ.get("MYSQL_USER", "test_user"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "test_password"),
        "HOST": os.environ.get("MYSQL_HOST", "localhost"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
    }
}
```

### Running Tests per Database

```bash
# SQLite (default)
pytest

# PostgreSQL
DJANGO_SETTINGS_MODULE=tests.settings.postgres pytest

# MySQL
DJANGO_SETTINGS_MODULE=tests.settings.mysql pytest
```

### Database-Specific Test Markers

Use pytest markers to run database-specific tests. The markers themselves are
declared in `pyproject.toml` under `[tool.pytest.ini_options]`, and `conftest.py`
contains the skip-by-database-vendor logic that deselects tests when the active
backend does not match the marker:

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "postgres: mark test as requiring PostgreSQL",
    "mysql: mark test as requiring MySQL",
]
```

```python
# In test files
@pytest.mark.postgres
def test_concurrent_index_on_postgres():
    """Test that SM010 only triggers on PostgreSQL."""
    ...
```

Run with markers:

```bash
# Skip PostgreSQL tests
pytest -m "not postgres"

# Only PostgreSQL tests
pytest -m postgres
```

______________________________________________________________________

## CI/CD Pipeline

### GitHub Actions Workflow

**.github/workflows/ci.yml:**

The CI workflow runs a Python x Django matrix on `ubuntu-latest`, with PostgreSQL
and MySQL services attached to every matrix job (so SQLite, PostgreSQL, and MySQL
are all exercised in a single test step). The matrix and its exclude rules mirror
the supported-versions table above.

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]
        django-version: ["3.2", "4.2", "5.0", "5.1", "6.0"]
        exclude:
          # Django 5.0+ requires Python 3.10+
          - python-version: "3.9"
            django-version: "5.0"
          - python-version: "3.9"
            django-version: "5.1"
          # Django 6.0 requires Python 3.12+
          - python-version: "3.9"
            django-version: "6.0"
          - python-version: "3.10"
            django-version: "6.0"
          - python-version: "3.11"
            django-version: "6.0"
          # Django 3.2 doesn't support Python 3.12+
          - python-version: "3.12"
            django-version: "3.2"
          - python-version: "3.13"
            django-version: "3.2"
          - python-version: "3.14"
            django-version: "3.2"
          # Django 4.2 doesn't support Python 3.14
          - python-version: "3.14"
            django-version: "4.2"
          # Django 5.0/5.1 don't support Python 3.14
          - python-version: "3.14"
            django-version: "5.0"
          - python-version: "3.14"
            django-version: "5.1"

    services:
      postgres:
        image: postgres:15
        # ...
      mysql:
        image: mysql:8.0
        # ...

    steps:
      - uses: actions/checkout@v6
      # Set up Python, install deps, then run SQLite / PostgreSQL / MySQL test steps.
      # Coverage is uploaded only on Python 3.12 + Django 4.2.
```

See the actual `.github/workflows/ci.yml` in the repository for the full configuration.

### Self-Hosted Runners

For testing on specific hardware or configurations:

```yaml
# .github/workflows/self-hosted.yml
name: Self-Hosted Tests

on:
  push:
    branches: [main]

jobs:
  test-arm:
    runs-on: [self-hosted, ARM64]
    steps:
      - uses: actions/checkout@v4
      - name: Run tests on ARM
        run: |
          python -m venv .venv
          source .venv/bin/activate
          pip install -e ".[dev]"
          pytest -v

  test-gpu:
    runs-on: [self-hosted, gpu]
    if: false # Enable when GPU tests are needed
    steps:
      - uses: actions/checkout@v4
      - name: Run GPU tests
        run: pytest -v -m gpu
```

______________________________________________________________________

## Coverage Requirements

### Minimum Coverage Thresholds

| Component          | Minimum Coverage |
| ------------------ | ---------------- |
| Overall            | 80%              |
| Core (analyzer.py) | 90%              |
| Rules              | 85%              |
| Reporters          | 75%              |
| Utils              | 70%              |

### Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["django_safe_migrations"]
branch = true
omit = [
    "*/migrations/*",
    "*/__pycache__/*",
    "*/tests/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
fail_under = 80
show_missing = true

[tool.coverage.html]
directory = "htmlcov"
```

### Viewing Coverage

```bash
# Generate HTML report
pytest --cov=django_safe_migrations --cov-report=html

# Open report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

______________________________________________________________________

## Adding New Tests

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures + DB-vendor skip logic
├── unit/                    # Unit tests (DB-specific tests gated by markers)
│   ├── rules/
│   │   ├── test_add_field_rules.py
│   │   ├── test_add_index_rules.py
│   │   └── test_remove_field_rules.py
│   ├── test_analyzer.py
│   └── test_reporters.py
├── integration/             # Integration tests (DB-specific tests gated by markers)
│   └── test_command.py
├── settings/                # Per-database test settings
│   ├── sqlite.py
│   ├── postgres.py
│   └── mysql.py
└── test_project/            # Test Django project
    ├── manage.py
    ├── settings.py
    └── testapp/
        └── migrations/
```

### Writing a New Test

```python
"""Tests for new feature."""

import pytest
from django.db import migrations, models

from django_safe_migrations.rules.new_rule import NewRule


class TestNewRule:
    """Tests for NewRule."""

    def test_detects_issue(self, mock_migration):
        """Test that rule detects the problematic pattern."""
        rule = NewRule()
        operation = migrations.SomeOperation(
            model_name="model",
            name="field",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM0XX"
        assert "expected message" in issue.message

    def test_ignores_safe_pattern(self, mock_migration):
        """Test that rule ignores safe patterns."""
        rule = NewRule()
        operation = migrations.SafeOperation()
        issue = rule.check(operation, mock_migration)

        assert issue is None

    @pytest.mark.postgres
    def test_postgres_specific(self):
        """Test PostgreSQL-specific behavior."""
        ...
```

### Fixture Guidelines

```python
# conftest.py

@pytest.fixture
def mock_migration():
    """Create a mock migration for testing."""
    class MockMigration:
        app_label = "testapp"
        name = "0001_test"
        operations = []
    return MockMigration()

@pytest.fixture
def not_null_field_operation():
    """Create a NOT NULL AddField operation."""
    return migrations.AddField(
        model_name="user",
        name="email",
        field=models.CharField(max_length=255),
    )
```

______________________________________________________________________

## Troubleshooting

### Common Issues

**1. Tests pass locally but fail in CI:**

- Check Python/Django version differences
- Ensure all dependencies are pinned
- Check for timezone/locale issues

**2. Database connection errors:**

- Verify service is running and healthy
- Check environment variables
- Ensure correct ports are exposed

**3. Import errors:**

- Run `pip install -e ".[dev]"` to reinstall
- Check for circular imports
- Verify `__init__.py` files exist

**4. Pre-commit failures:**

- Run `pre-commit run --all-files` to see details
- Use `git add -A` before running pre-commit
- Check for formatting issues in new files

### Getting Help

- Open an issue: https://github.com/YasserShkeir/django-safe-migrations/issues
- Check existing discussions
- Review CI logs for detailed error messages

______________________________________________________________________

## Summary

This testing strategy ensures `django-safe-migrations` is:

1. **Reliable** - Comprehensive unit and integration tests
2. **Compatible** - Matrix testing across Python/Django versions
3. **Portable** - Docker for consistent environments
4. **Database-agnostic** - Tests on SQLite, PostgreSQL, MySQL
5. **Maintainable** - Pre-commit hooks enforce code quality
6. **Documented** - Clear guidelines for contributors

By following this guide, you can run tests locally, in Docker, or via CI/CD to ensure
the library works correctly across all supported configurations.
