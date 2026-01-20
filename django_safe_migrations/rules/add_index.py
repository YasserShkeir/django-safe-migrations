"""Rules for AddIndex and AddConstraint operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation

logger = logging.getLogger("django_safe_migrations")


class UnsafeIndexCreationRule(BaseRule):
    """Detect index creation that will block writes.

    Creating an index on PostgreSQL takes an ACCESS EXCLUSIVE lock
    on the table, blocking all reads and writes until complete.

    For large tables, this can take minutes or hours.

    Safe pattern (PostgreSQL):
    - Use AddIndexConcurrently from django.contrib.postgres.operations
    - Or create the index manually with CONCURRENTLY option
    """

    rule_id = "SM010"
    severity = Severity.ERROR
    description = "Index creation without CONCURRENTLY will lock table"
    db_vendors = ["postgresql"]  # Only applies to PostgreSQL

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation creates an index without CONCURRENTLY.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include db_vendor).

        Returns:
            An Issue if the operation is unsafe, None otherwise.
        """
        # Check for standard AddIndex
        if isinstance(operation, migrations.AddIndex):
            # Check if it's a concurrent index operation
            if self._is_concurrent_operation(operation):
                return None

            index = getattr(operation, "index", None)
            index_name = getattr(index, "name", "unknown") if index else "unknown"
            model_name = getattr(operation, "model_name", "unknown")

            return self.create_issue(
                operation=operation,
                message=(
                    f"Creating index '{index_name}' on '{model_name}' "
                    f"will lock the table for writes"
                ),
                migration=migration,
            )

        return None

    def _is_concurrent_operation(self, operation: Operation) -> bool:
        """Check if the operation uses concurrent index creation.

        Args:
            operation: The operation to check.

        Returns:
            True if concurrent, False otherwise.
        """
        # Check for AddIndexConcurrently from django.contrib.postgres
        op_class_name = type(operation).__name__
        if op_class_name == "AddIndexConcurrently":
            return True

        # Check for custom concurrent flag
        if getattr(operation, "concurrently", False):
            return True

        return False

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        index = getattr(operation, "index", None)
        index_name = getattr(index, "name", "my_index") if index else "my_index"
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for creating an index on PostgreSQL:

1. Use AddIndexConcurrently (requires atomic=False):
   from django.contrib.postgres.operations import AddIndexConcurrently

   class Migration(migrations.Migration):
       atomic = False  # Required for concurrent operations

       operations = [
           AddIndexConcurrently(
               model_name='{model_name}',
               index=models.Index(fields=['field_name'], name='{index_name}'),
           ),
       ]

Note: CONCURRENTLY takes longer but doesn't lock the table.
The migration must have atomic=False.
"""


class UnsafeUniqueConstraintRule(BaseRule):
    """Detect unique constraint that will block writes.

    Adding a unique constraint requires PostgreSQL to:
    1. Create a unique index (blocking writes)
    2. Validate all existing rows

    Safe pattern (PostgreSQL):
    1. Create a unique index concurrently first
    2. Add the constraint using the existing index
    """

    rule_id = "SM011"
    severity = Severity.ERROR
    description = "Unique constraint without concurrent index will lock table"
    db_vendors = ["postgresql"]  # Only applies to PostgreSQL

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a unique constraint unsafely.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation is unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AddConstraint):
            return None

        constraint = getattr(operation, "constraint", None)
        if constraint is None:
            return None

        # Check if it's a UniqueConstraint
        constraint_class = type(constraint).__name__
        if constraint_class != "UniqueConstraint":
            return None

        constraint_name = getattr(constraint, "name", "unknown")
        model_name = getattr(operation, "model_name", "unknown")

        return self.create_issue(
            operation=operation,
            message=(
                f"Adding unique constraint '{constraint_name}' on '{model_name}' "
                f"will lock the table"
            ),
            migration=migration,
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        constraint = getattr(operation, "constraint", None)
        constraint_name = (
            getattr(constraint, "name", "unique_constraint")
            if constraint
            else "unique_constraint"
        )
        model_name = getattr(operation, "model_name", "model")
        fields = (
            getattr(constraint, "fields", ["field_name"])
            if constraint
            else ["field_name"]
        )
        fields_str = ", ".join(f"'{f}'" for f in fields)

        return f"""Safe pattern for adding a unique constraint on PostgreSQL:

1. Migration 1 - Create unique index concurrently (atomic=False):
   from django.contrib.postgres.operations import AddIndexConcurrently

   class Migration(migrations.Migration):
       atomic = False

       operations = [
           AddIndexConcurrently(
               model_name='{model_name}',
               index=models.Index(
                   fields=[{fields_str}],
                   name='{constraint_name}_idx',
               ),
           ),
       ]

2. Migration 2 - Add constraint using existing index:
   Use raw SQL to add the constraint using the existing index:

   migrations.RunSQL(
       sql='ALTER TABLE {model_name} ADD CONSTRAINT {constraint_name} '
           'UNIQUE USING INDEX {constraint_name}_idx',
       reverse_sql='ALTER TABLE {model_name} DROP CONSTRAINT {constraint_name}',
   )

Note: This approach adds the constraint without rebuilding the index.
"""


class ConcurrentInAtomicMigrationRule(BaseRule):
    """Detect concurrent operations in atomic migrations.

    AddIndexConcurrently and RemoveIndexConcurrently require the migration
    to have atomic = False. PostgreSQL cannot run concurrent operations
    inside a transaction, so Django must disable transaction wrapping.

    If atomic is not explicitly set to False, the migration will fail
    at runtime with an error like:
        "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"

    Safe pattern:
    - Set atomic = False on the Migration class when using concurrent operations
    """

    rule_id = "SM018"
    severity = Severity.ERROR
    description = "Concurrent operations require atomic = False"
    db_vendors = ["postgresql"]

    # Concurrent operation class names to detect
    CONCURRENT_OPERATIONS = frozenset(
        {
            "AddIndexConcurrently",
            "RemoveIndexConcurrently",
        }
    )

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if concurrent operation is in an atomic migration.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the migration is atomic, None otherwise.
        """
        op_class_name = type(operation).__name__

        # Check if this is a concurrent operation
        if op_class_name not in self.CONCURRENT_OPERATIONS:
            return None

        # Check if migration has atomic = False
        # Default is True (atomic), so we need explicit False
        is_atomic = getattr(migration, "atomic", True)

        if is_atomic:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"{op_class_name} requires Migration.atomic = False. "
                    f"Concurrent operations cannot run inside a transaction."
                ),
            )

        logger.debug(
            "Concurrent operation %s has atomic=False - OK",
            op_class_name,
        )
        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for fixing the migration.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested fix.
        """
        op_class_name = type(operation).__name__
        model_name = getattr(operation, "model_name", "model")

        return f"""Fix: Set atomic = False on the Migration class.

PostgreSQL concurrent operations (like {op_class_name}) cannot run
inside a transaction. Django must be told to not wrap the migration
in a transaction.

Correct migration:
   from django.contrib.postgres.operations import {op_class_name}

   class Migration(migrations.Migration):
       atomic = False  # Required for concurrent operations!

       dependencies = [...]

       operations = [
           {op_class_name}(
               model_name='{model_name}',
               ...
           ),
       ]

Note: When atomic = False, each operation runs in its own transaction.
If any operation fails, previous operations will NOT be rolled back.
"""
