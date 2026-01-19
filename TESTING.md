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

- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Django versions**: 3.2, 4.2, 5.0, 5.1
- **Database backends**: SQLite, PostgreSQL, MySQL/MariaDB
- **Operating systems**: Linux (Ubuntu), macOS, Windows

### Test Types

| Type              | Purpose                                 | Location             | Run Frequency |
| ----------------- | --------------------------------------- | -------------------- | ------------- |
| Unit Tests        | Test individual components in isolation | `tests/unit/`        | Every commit  |
| Integration Tests | Test components working together        | `tests/integration/` | Every commit  |
| Database Tests    | Test database-specific behavior         | `tests/database/`    | CI matrix     |
| End-to-End Tests  | Test complete workflows                 | `tests/e2e/`         | PR/Release    |

______________________________________________________________________

## Test Matrix

### Python × Django Compatibility Matrix

```
             │ Django 3.2 │ Django 4.2 │ Django 5.0 │ Django 5.1 │
─────────────┼────────────┼────────────┼────────────┼────────────┤
Python 3.9   │     ✅     │     ✅     │     ❌     │     ❌     │
Python 3.10  │     ✅     │     ✅     │     ✅     │     ✅     │
Python 3.11  │     ✅     │     ✅     │     ✅     │     ✅     │
Python 3.12  │     ❌     │     ✅     │     ✅     │     ✅     │
Python 3.13  │     ❌     │     ✅     │     ✅     │     ✅     │
```

**Note**: Django 5.x requires Python 3.10+; Django 3.2 doesn't support Python 3.12+.

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
envlist =
    py39-django{32,42}
    py310-django{32,42,50,51}
    py311-django{32,42,50,51}
    py312-django{42,50,51}
    py313-django{42,50,51}
    lint
    type-check

[testenv]
deps =
    django32: Django>=3.2,<4.0
    django42: Django>=4.2,<5.0
    django50: Django>=5.0,<5.1
    django51: Django>=5.1,<5.2
    pytest>=7.0
    pytest-django>=4.5
    pytest-cov>=4.0
commands =
    pytest {posargs:tests/}

[testenv:lint]
deps = pre-commit
commands = pre-commit run --all-files

[testenv:type-check]
deps =
    mypy>=1.0
    django-stubs>=4.0
commands = mypy django_safe_migrations/
```

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
make coverage

# Run linting
make lint

# Run type checking
make type-check

# Run all checks
make check
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
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  # MySQL Database
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: test_db
      MYSQL_USER: test_user
      MYSQL_PASSWORD: test_password
      MYSQL_ROOT_PASSWORD: root_password
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Test runner - Python 3.11
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
      - DATABASE_URL=postgres://test_user:test_password@postgres:5432/test_db
      - MYSQL_URL=mysql://test_user:test_password@mysql:3306/test_db
    volumes:
      - .:/app
    command: pytest -v --cov=django_safe_migrations

  # Test runner - Python 3.12
  test-py312:
    build:
      context: .
      dockerfile: Dockerfile.test
      args:
        PYTHON_VERSION: "3.12"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgres://test_user:test_password@postgres:5432/test_db
    volumes:
      - .:/app
    command: pytest -v

  # Test runner - Python 3.13
  test-py313:
    build:
      context: .
      dockerfile: Dockerfile.test
      args:
        PYTHON_VERSION: "3.13"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgres://test_user:test_password@postgres:5432/test_db
    volumes:
      - .:/app
    command: pytest -v
```

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

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev,postgres,mysql]"

# Copy source code
COPY . .

# Run tests by default
CMD ["pytest", "-v"]
```

### Running Docker Tests

```bash
# Run all tests with all databases
docker-compose -f docker-compose.test.yml up --build

# Run specific Python version
docker-compose -f docker-compose.test.yml up test-py312 --build

# Run with specific database only
docker-compose -f docker-compose.test.yml up postgres test-py311 --build

# Clean up
docker-compose -f docker-compose.test.yml down -v
```

______________________________________________________________________

## Multi-Database Backend Testing

### Database-Specific Rules

Some rules only apply to specific databases:

| Rule                        | SQLite | PostgreSQL | MySQL |
| --------------------------- | ------ | ---------- | ----- |
| SM001 (NOT NULL)            | ✅     | ✅         | ✅    |
| SM002 (Drop Column)         | ✅     | ✅         | ✅    |
| SM003 (Drop Table)          | ✅     | ✅         | ✅    |
| SM010 (Index CONCURRENTLY)  | ❌     | ✅         | ❌    |
| SM011 (Unique CONCURRENTLY) | ❌     | ✅         | ❌    |

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

Use pytest markers to run database-specific tests:

```python
# In conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: mark test as requiring PostgreSQL"
    )
    config.addinivalue_line(
        "markers", "mysql: mark test as requiring MySQL"
    )

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

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install pre-commit
        run: pip install pre-commit
      - name: Run pre-commit
        run: pre-commit run --all-files

  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
        django-version: ["3.2", "4.2", "5.0", "5.1"]
        exclude:
          # Django 5.x requires Python 3.10+
          - python-version: "3.9"
            django-version: "5.0"
          - python-version: "3.9"
            django-version: "5.1"
          # Django 3.2 doesn't support Python 3.12+
          - python-version: "3.12"
            django-version: "3.2"
          - python-version: "3.13"
            django-version: "3.2"

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install Django~=${{ matrix.django-version }}.0
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest -v --cov=django_safe_migrations --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: matrix.python-version == '3.11' && matrix.django-version == '4.2'

  test-postgres:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[dev,postgres]"

      - name: Run PostgreSQL tests
        env:
          DJANGO_SETTINGS_MODULE: tests.settings.postgres
          POSTGRES_HOST: localhost
          POSTGRES_PORT: 5432
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        run: pytest -v -m postgres

  test-mysql:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_DATABASE: test_db
          MYSQL_USER: test_user
          MYSQL_PASSWORD: test_password
          MYSQL_ROOT_PASSWORD: root_password
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[dev,mysql]"

      - name: Run MySQL tests
        env:
          DJANGO_SETTINGS_MODULE: tests.settings.mysql
          MYSQL_HOST: 127.0.0.1
          MYSQL_PORT: 3306
          MYSQL_DB: test_db
          MYSQL_USER: test_user
          MYSQL_PASSWORD: test_password
        run: pytest -v -m mysql
```

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
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── rules/
│   │   ├── test_add_field_rules.py
│   │   ├── test_add_index_rules.py
│   │   └── test_remove_field_rules.py
│   ├── test_analyzer.py
│   └── test_reporters.py
├── integration/             # Integration tests
│   └── test_command.py
├── database/                # Database-specific tests
│   ├── test_postgres.py
│   └── test_mysql.py
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

- Open an issue: https://github.com/username/django-safe-migrations/issues
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
