"""Rules for RemoveField and DeleteModel operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class DropColumnUnsafeRule(BaseRule):
    """Detect dropping a column that may still be referenced by code.

    Dropping a column is dangerous because:
    1. Old code may still reference the column (during deployment)
    2. The operation is irreversible (data is lost)
    3. Rollback won't restore the column data

    Safe pattern (expand/contract):
    1. Remove all code references to the column
    2. Deploy and ensure no queries reference the column
    3. Drop the column in a later release
    """

    rule_id = "SM002"
    severity = Severity.WARNING
    description = "Dropping column while old code may reference it"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation drops a column.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue warning about the operation, None otherwise.
        """
        if not isinstance(operation, migrations.RemoveField):
            return None

        model_name = getattr(operation, "model_name", "unknown")
        field_name = getattr(operation, "name", "unknown")

        return self.create_issue(
            operation=operation,
            message=(
                f"Dropping column '{field_name}' from '{model_name}' - "
                "ensure all code references have been removed first"
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
        field_name = getattr(operation, "name", "field_name")
        _ = getattr(operation, "model_name", "model")  # For future use

        return f"""Safe pattern for dropping a column (expand/contract):

1. Release 1 - Stop writing to the column:
   - Remove all code that writes to '{field_name}'
   - Keep the column in the model (null=True if needed)
   - Deploy and verify no writes occur

2. Release 2 - Stop reading the column:
   - Remove all code that reads from '{field_name}'
   - Remove the field from the model
   - Deploy and verify no queries reference the column

3. Release 3 - Drop the column:
   - Create migration to remove the column
   - This migration is now safe to run

Tip: Use database query logs to verify no queries reference the column.
"""


class DropTableUnsafeRule(BaseRule):
    """Detect dropping a table that may still be referenced by code.

    Dropping a table is dangerous because:
    1. Old code may still reference the table (during deployment)
    2. Foreign keys from other tables may exist
    3. The operation is irreversible (data is lost)

    Safe pattern:
    1. Remove all code references to the model
    2. Remove any foreign keys referencing the table
    3. Deploy and ensure no queries reference the table
    4. Drop the table in a later release
    """

    rule_id = "SM003"
    severity = Severity.WARNING
    description = "Dropping table while old code may reference it"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation drops a table.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue warning about the operation, None otherwise.
        """
        if not isinstance(operation, migrations.DeleteModel):
            return None

        model_name = getattr(operation, "name", "unknown")

        return self.create_issue(
            operation=operation,
            message=(
                f"Dropping table for model '{model_name}' - "
                f"ensure all code references and foreign keys have been removed first"
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
        model_name = getattr(operation, "name", "Model")

        return f"""Safe pattern for dropping a table (expand/contract):

1. Release 1 - Stop using the model:
   - Remove all code that reads from or writes to '{model_name}'
   - Remove any ForeignKey/OneToOneField references to '{model_name}'
   - Deploy and verify no queries reference the table

2. Release 2 - Remove foreign key constraints:
   - Create migrations to remove FK constraints from related tables
   - Deploy and verify no constraint violations

3. Release 3 - Drop the table:
   - Remove the model from models.py
   - Create migration to delete the model
   - This migration is now safe to run

Tip: Check for any raw SQL queries that reference the table.
"""
