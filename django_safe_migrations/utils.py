"""Utility functions for django-safe-migrations."""

from __future__ import annotations

import ast
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.migrations import Migration

logger = logging.getLogger("django_safe_migrations")


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
    """Get the line number of an operation in a migration file using AST parsing.

    Uses Python's AST module to accurately locate operations in migration files,
    handling comments, multi-line strings, and complex formatting correctly.

    Args:
        migration: A Django migration instance.
        operation_index: The index of the operation in the operations list.

    Returns:
        The line number (1-indexed), or None if not found.
    """
    file_path = get_migration_file_path(migration)
    if not file_path or not os.path.exists(file_path):
        logger.debug("Migration file not found: %s", file_path)
        return None

    # Try AST-based detection first
    line_number = _get_operation_line_number_ast(file_path, operation_index)
    if line_number is not None:
        return line_number

    # Fall back to bracket-counting for edge cases
    logger.debug("AST parsing failed, falling back to bracket counting")
    return _get_operation_line_number_fallback(file_path, operation_index)


def _get_operation_line_number_ast(file_path: str, operation_index: int) -> int | None:
    """Get operation line number using AST parsing.

    Args:
        file_path: Path to the migration file.
        operation_index: The index of the operation in the operations list.

    Returns:
        The line number (1-indexed), or None if not found.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the Migration class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Migration":
                # Find operations = [...] assignment
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "operations"
                            ):
                                # Get the list elements
                                if isinstance(item.value, ast.List):
                                    elements = item.value.elts
                                    if operation_index < len(elements):
                                        return elements[operation_index].lineno
                                    logger.debug(
                                        "Operation index %d out of range "
                                        "(list has %d elements)",
                                        operation_index,
                                        len(elements),
                                    )
                                    return None
        logger.debug("Could not find Migration class or operations list in AST")
        return None

    except SyntaxError as e:
        logger.debug("Syntax error parsing migration file: %s", e)
        return None
    except OSError as e:
        logger.debug("Could not read migration file: %s", e)
        return None


def _get_operation_line_number_fallback(
    file_path: str, operation_index: int
) -> int | None:
    """Fallback line number detection using bracket counting.

    This is a simpler approach that may fail on complex migrations
    but provides a fallback when AST parsing fails.

    Args:
        file_path: Path to the migration file.
        operation_index: The index of the operation in the operations list.

    Returns:
        The line number (1-indexed), or None if not found.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
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

    except OSError as e:
        logger.debug("Could not read migration file for fallback parsing: %s", e)

    return None


def get_operation_column_number(
    migration: Migration, operation_index: int
) -> int | None:
    """Get the column number of an operation in a migration file.

    Uses AST parsing to get accurate column positions for SARIF reporting.

    Args:
        migration: A Django migration instance.
        operation_index: The index of the operation in the operations list.

    Returns:
        The column number (0-indexed), or None if not found.
    """
    file_path = get_migration_file_path(migration)
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Migration":
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "operations"
                            ):
                                if isinstance(item.value, ast.List):
                                    elements = item.value.elts
                                    if operation_index < len(elements):
                                        return elements[operation_index].col_offset
        return None

    except (SyntaxError, OSError):
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

        vendor = connection.vendor
        # Normalize PostGIS to postgresql so vendor-specific rules still apply
        if vendor == "postgis":
            return "postgresql"
        return vendor
    except Exception:
        logger.warning(
            "Could not determine database vendor; "
            "all vendor-specific rules will be skipped",
            exc_info=True,
        )
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

    for (app, name), migration in loader.disk_migrations.items():
        if app == app_label:
            migrations.append((name, migration))

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


def resolve_field_before_operation(
    app_label: str,
    migration_name: str,
    operation_index: int,
    model_name: str,
    field_name: str,
) -> Any:
    """Resolve the field definition before an AlterField operation.

    Uses Django's migration state resolver to build the project state
    up to (but not including) the target operation, then extracts the
    field definition from the model state.

    Args:
        app_label: The app label (e.g., 'myapp').
        migration_name: The migration name (e.g., '0002_alter_field').
        operation_index: The index of the operation within the migration.
        model_name: The model name (lowercase).
        field_name: The field name.

    Returns:
        The old field instance, or None if it cannot be resolved.
    """
    try:
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(None, ignore_no_migrations=True)
        migration_key = (app_label, migration_name)

        if migration_key not in loader.disk_migrations:
            logger.debug("Migration %s not in disk_migrations", migration_key)
            return None

        # Skip if migration is not in the graph (e.g., replaced by a
        # squashed migration). project_state() requires graph membership.
        if migration_key not in loader.graph.nodes:
            logger.debug(
                "Migration %s not in graph (possibly replaced/squashed)",
                migration_key,
            )
            return None

        # Build state up to (but not including) this migration
        state = loader.project_state(migration_key, at_end=False)

        # If the operation isn't the first one, replay earlier operations
        # in the same migration to get the exact state before this op
        if operation_index > 0:
            migration = loader.disk_migrations[migration_key]
            operations = getattr(migration, "operations", [])
            for i in range(min(operation_index, len(operations))):
                operations[i].state_forwards(app_label, state)

        # Look up the model state
        model_key = (app_label, model_name)
        model_state = state.models.get(model_key)
        if model_state is None:
            logger.debug("Model %s not found in state", model_key)
            return None

        # Look up the field in the model state
        # Django 4.2+ uses a dict; older versions use a list of tuples
        fields = model_state.fields
        if isinstance(fields, dict):
            return fields.get(field_name)
        for name, field in fields:
            if name == field_name:
                return field

        logger.debug("Field %s not found in model %s", field_name, model_key)
        return None

    except Exception as e:  # noqa: BLE001
        logger.debug("Could not resolve old field state: %s", e)
        return None
