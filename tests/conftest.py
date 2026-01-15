"""Pytest configuration and fixtures for django-safe-migrations tests."""

from __future__ import annotations

import pytest
from django.db import connection, migrations, models


def pytest_runtest_setup(item):
    """Skip tests based on database markers."""
    markers = list(item.iter_markers())
    postgres_marker = any(m.name == "postgres" for m in markers)
    mysql_marker = any(m.name == "mysql" for m in markers)

    db_vendor = connection.vendor

    if postgres_marker and db_vendor != "postgresql":
        pytest.skip("Test requires PostgreSQL")
    if mysql_marker and db_vendor != "mysql":
        pytest.skip("Test requires MySQL")


@pytest.fixture
def not_null_field_operation():
    """Create an AddField operation with NOT NULL and no default."""
    return migrations.AddField(
        model_name="user",
        name="email",
        field=models.CharField(max_length=255),
    )


@pytest.fixture
def nullable_field_operation():
    """Create an AddField operation with null=True."""
    return migrations.AddField(
        model_name="user",
        name="nickname",
        field=models.CharField(max_length=255, null=True),
    )


@pytest.fixture
def field_with_default_operation():
    """Create an AddField operation with a default value."""
    return migrations.AddField(
        model_name="user",
        name="status",
        field=models.CharField(max_length=50, default="active"),
    )


@pytest.fixture
def remove_field_operation():
    """Create a RemoveField operation."""
    return migrations.RemoveField(
        model_name="user",
        name="old_field",
    )


@pytest.fixture
def delete_model_operation():
    """Create a DeleteModel operation."""
    return migrations.DeleteModel(name="OldModel")


@pytest.fixture
def add_index_operation():
    """Create an AddIndex operation."""
    return migrations.AddIndex(
        model_name="user",
        index=models.Index(fields=["email"], name="user_email_idx"),
    )


@pytest.fixture
def add_unique_constraint_operation():
    """Create an AddConstraint operation with UniqueConstraint."""
    return migrations.AddConstraint(
        model_name="user",
        constraint=models.UniqueConstraint(
            fields=["email"],
            name="unique_user_email",
        ),
    )


class MockMigration:
    """Mock migration for testing."""

    def __init__(
        self,
        app_label: str = "testapp",
        name: str = "0001_initial",
        operations: list | None = None,
    ):
        """Initialize mock migration.

        Args:
            app_label: The app label.
            name: The migration name.
            operations: List of operations.
        """
        self.app_label = app_label
        self.name = name
        self.operations = operations or []


@pytest.fixture
def mock_migration():
    """Create a mock migration."""
    return MockMigration()


@pytest.fixture
def mock_migration_factory():
    """Create factory fixture to create mock migrations with custom operations."""

    def _create(operations: list, app_label: str = "testapp", name: str = "0001_test"):
        return MockMigration(
            app_label=app_label,
            name=name,
            operations=operations,
        )

    return _create
