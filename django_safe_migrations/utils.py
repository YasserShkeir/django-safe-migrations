"""Utility functions for django-safe-migrations."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.migrations import Migration


def get_migration_file_path(migration: Migration) -> str | None:
    """Get the file path of a migration.

    Args:
        migration: A Django migration instance.

    Returns:
        The file path of the migration, or None if not found.
    """
    if hasattr(migration, "__module__"):
        module = migration.__module__
        try:
            import importlib

            mod = importlib.import_module(module)
            if hasattr(mod, "__file__") and mod.__file__:
                return mod.__file__
        except ImportError:
            pass
    return None


def get_operation_line_number(migration: Migration, operation_index: int) -> int | None:
    """Get the approximate line number of an operation in a migration file.

    This is a best-effort function that parses the migration file
    to find where an operation is defined.

    Args:
        migration: A Django migration instance.
        operation_index: The index of the operation in the operations list.

    Returns:
        The line number, or None if not found.
    """
    file_path = get_migration_file_path(migration)
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        operations_start = None
        bracket_depth = 0
        current_operation = -1

        for i, line in enumerate(lines, start=1):
            if "operations = [" in line or "operations=[" in line:
                operations_start = i
                bracket_depth = line.count("[") - line.count("]")
                continue

            if operations_start is not None:
                # Track nested brackets
                bracket_depth += line.count("[") - line.count("]")

                # Look for operation class names
                stripped = line.strip()
                if stripped.startswith("migrations.") or stripped.startswith(
                    "operations."
                ):
                    current_operation += 1
                    if current_operation == operation_index:
                        return i

                if bracket_depth <= 0:
                    break

    except (OSError, IOError):
        pass

    return None


def format_operation_name(operation: Any) -> str:
    """Format an operation for display.

    Args:
        operation: A Django migration operation.

    Returns:
        A formatted string representation.
    """
    op_type = type(operation).__name__

    if hasattr(operation, "model_name") and hasattr(operation, "name"):
        return f"{op_type}({operation.model_name}.{operation.name})"
    elif hasattr(operation, "model_name"):
        return f"{op_type}({operation.model_name})"
    elif hasattr(operation, "name"):
        return f"{op_type}({operation.name})"

    return op_type


def get_db_vendor() -> str:
    """Get the database vendor from Django settings.

    Returns:
        The database vendor string (e.g., 'postgresql', 'mysql', 'sqlite').
    """
    try:
        from django.db import connection

        return connection.vendor
    except Exception:
        return "unknown"


def is_postgres() -> bool:
    """Check if the database is PostgreSQL.

    Returns:
        True if using PostgreSQL, False otherwise.
    """
    return get_db_vendor() == "postgresql"


def is_mysql() -> bool:
    """Check if the database is MySQL/MariaDB.

    Returns:
        True if using MySQL or MariaDB, False otherwise.
    """
    return get_db_vendor() in ("mysql", "mariadb")


def is_sqlite() -> bool:
    """Check if the database is SQLite.

    Returns:
        True if using SQLite, False otherwise.
    """
    return get_db_vendor() == "sqlite"


def get_app_migrations(app_label: str) -> list[tuple[str, Any]]:
    """Get all migrations for a Django app.

    Args:
        app_label: The app label (e.g., 'myapp').

    Returns:
        A list of tuples (migration_name, migration_class).
    """
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(None, ignore_no_migrations=True)
    migrations = []

    for app, name in loader.disk_migrations.keys():
        if app == app_label:
            migrations.append((name, loader.get_migration(app, name)))

    # Sort by migration name
    migrations.sort(key=lambda x: x[0])
    return migrations


def get_unapplied_migrations(app_label: str | None = None) -> list[tuple[str, str]]:
    """Get migrations that haven't been applied yet.

    Args:
        app_label: Optional app label to filter by.

    Returns:
        A list of tuples (app_label, migration_name).
    """
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.recorder import MigrationRecorder

    loader = MigrationLoader(connection)
    recorder = MigrationRecorder(connection)
    applied = recorder.applied_migrations()

    unapplied = []
    for key in loader.disk_migrations.keys():
        if key not in applied:
            if app_label is None or key[0] == app_label:
                unapplied.append(key)

    return sorted(unapplied)
