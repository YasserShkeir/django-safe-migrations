"""Migration-level rules that reason over all operations together."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity
from django_safe_migrations.rules.run_sql import _split_sql_statements

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation

# Operations that change the database schema.
_SCHEMA_OP_TYPES = (
    migrations.AddField,
    migrations.RemoveField,
    migrations.AlterField,
    migrations.RenameField,
    migrations.AddIndex,
    migrations.RemoveIndex,
    migrations.AddConstraint,
    migrations.RemoveConstraint,
    migrations.CreateModel,
    migrations.DeleteModel,
    migrations.RenameModel,
)

# Heavy, potentially table-locking schema operations (excludes cheap/metadata
# ops like RenameField and brand-new CreateModel).
_HEAVY_OP_TYPES = (
    migrations.AddField,
    migrations.RemoveField,
    migrations.AlterField,
    migrations.AddIndex,
    migrations.RemoveIndex,
    migrations.AddConstraint,
    migrations.RemoveConstraint,
)

_DML_RE = re.compile(r"(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)


def _is_schema_op(operation: object) -> bool:
    """Return True if the operation alters the database schema."""
    return isinstance(operation, _SCHEMA_OP_TYPES)


def _is_data_op(operation: object) -> bool:
    """Return True if the operation manipulates data (RunPython/RunSQL DML)."""
    if isinstance(operation, migrations.RunPython):
        return True
    if isinstance(operation, migrations.RunSQL):
        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            if _DML_RE.match(statement):
                return True
    return False


def _model_key(operation: object) -> str | None:
    """Return a normalized model identifier for an operation, if any."""
    name = getattr(operation, "model_name", None) or getattr(operation, "name", None)
    return str(name).lower() if name else None


class MixedSchemaAndDataRule(BaseRule):
    """Detect a migration that mixes schema changes with data operations.

    Combining schema changes (AddField, AlterField, …) with data operations
    (RunPython, or RunSQL containing DML) in one migration extends the lock
    held during the data step and, on PostgreSQL, can raise
    ``cannot ALTER TABLE because it has pending trigger events``. Split schema
    and data into separate migrations.
    """

    rule_id = "SM038"
    severity = Severity.WARNING
    description = "Migration mixes schema changes with data operations"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Per-operation check is unused; this is a migration-level rule."""
        return None

    def check_migration(self, migration: Migration) -> list[Issue]:
        """Flag a migration that contains both schema and data operations."""
        operations = getattr(migration, "operations", [])
        has_schema = any(_is_schema_op(op) for op in operations)
        has_data = any(_is_data_op(op) for op in operations)
        if has_schema and has_data:
            return [
                Issue(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    operation="Migration",
                    message=(
                        "Migration mixes schema changes with data operations "
                        "(RunPython/RunSQL DML). Split them into separate "
                        "migrations to reduce lock duration and avoid pending "
                        "trigger event errors."
                    ),
                )
            ]
        return []


class MultipleHeavyOpsSameTableRule(BaseRule):
    """Detect several heavy schema operations on the same table in one migration.

    When a migration runs three or more heavy schema operations against the same
    table, the table lock is held for their combined duration. Splitting them
    into separate migrations reduces lock time and deadlock risk.
    """

    rule_id = "SM054"
    severity = Severity.INFO
    description = "Several heavy schema operations on one table in a migration"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Per-operation check is unused; this is a migration-level rule."""
        return None

    def check_migration(self, migration: Migration) -> list[Issue]:
        """Flag 3+ heavy ops on the same table."""
        counts: dict[str, int] = defaultdict(int)
        for op in getattr(migration, "operations", []):
            if isinstance(op, _HEAVY_OP_TYPES):
                key = _model_key(op)
                if key:
                    counts[key] += 1

        for model, count in counts.items():
            if count >= 3:
                return [
                    Issue(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        operation="Migration",
                        message=(
                            f"Migration has {count} heavy schema operations on "
                            f"'{model}'. The table lock is held for their combined "
                            "duration — consider splitting into separate "
                            "migrations."
                        ),
                    )
                ]
        return []
