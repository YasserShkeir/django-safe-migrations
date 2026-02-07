"""Rules for constraint operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class AddUniqueConstraintRule(BaseRule):
    """Detect adding a unique constraint that requires table scan.

    Adding a unique constraint on a table with data requires:
    1. A full table scan to validate existing rows
    2. Creating a unique index (blocking writes on PostgreSQL)

    For large tables, this can cause significant downtime.

    Safe pattern (PostgreSQL):
    1. Create a unique index concurrently first
    2. Add the constraint using the existing index
    """

    rule_id = "SM009"
    severity = Severity.ERROR
    description = "Adding unique constraint requires full table scan"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a unique constraint.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include db_vendor).

        Returns:
            An Issue if the operation is unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AddConstraint):
            return None

        constraint = getattr(operation, "constraint", None)
        if constraint is None:
            return None

        # Check if it's a UniqueConstraint
        constraint_class_name = type(constraint).__name__
        if constraint_class_name != "UniqueConstraint":
            return None

        # On PostgreSQL, SM011 provides a more specific warning with
        # concurrent index advice — skip to avoid duplicate issues.
        db_vendor: str | None = kwargs.get("db_vendor")  # type: ignore[assignment]
        if db_vendor == "postgresql":
            return None

        constraint_name = getattr(constraint, "name", "unknown")
        model_name = getattr(operation, "model_name", "unknown")
        fields = getattr(constraint, "fields", [])
        fields_str = ", ".join(fields) if fields else "unknown"

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding unique constraint '{constraint_name}' on "
                f"'{model_name}' ({fields_str}) requires full table scan "
                f"and will block writes"
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        constraint = getattr(operation, "constraint", None)
        constraint_name = getattr(constraint, "name", "unique_constraint")
        model_name = getattr(operation, "model_name", "model")
        fields = getattr(constraint, "fields", ["field"])

        return f"""Safe pattern for adding unique constraint:

1. First, create a unique index concurrently:
   from django.contrib.postgres.operations import AddIndexConcurrently

   class Migration(migrations.Migration):
       atomic = False

       operations = [
           AddIndexConcurrently(
               model_name='{model_name}',
               index=models.Index(
                   fields={fields!r},
                   name='{constraint_name}_idx',
               ),
           ),
       ]

2. Then, add the constraint using the existing index:
   migrations.AddConstraint(
       model_name='{model_name}',
       constraint=models.UniqueConstraint(
           fields={fields!r},
           name='{constraint_name}',
       ),
   )

Note: PostgreSQL will use the existing index instead of creating a new one.
"""


class AlterUniqueTogetherRule(BaseRule):
    """Detect usage of deprecated AlterUniqueTogether.

    AlterUniqueTogether is deprecated since Django 4.0.
    Use AddConstraint with UniqueConstraint instead.

    This operation also requires a table scan to validate uniqueness.
    """

    rule_id = "SM015"
    severity = Severity.WARNING
    description = "AlterUniqueTogether is deprecated, use UniqueConstraint"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation uses AlterUniqueTogether.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if AlterUniqueTogether is used, None otherwise.
        """
        if not isinstance(operation, migrations.AlterUniqueTogether):
            return None

        model_name = getattr(operation, "name", "unknown")
        unique_together = getattr(operation, "unique_together", None)

        # If removing unique_together (setting to empty), that's fine
        if not unique_together:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"AlterUniqueTogether on '{model_name}' is deprecated. "
                f"Use AddConstraint with UniqueConstraint instead."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        model_name = getattr(operation, "name", "model")
        unique_together = getattr(operation, "unique_together", {("field1", "field2")})
        # unique_together is a set, convert to list first
        fields_tuple = next(iter(unique_together), ("field1", "field2"))
        fields = list(fields_tuple)

        return f"""Replace AlterUniqueTogether with UniqueConstraint:

# Instead of:
migrations.AlterUniqueTogether(
    name='{model_name}',
    unique_together={{('field1', 'field2')}},
)

# Use:
migrations.AddConstraint(
    model_name='{model_name}',
    constraint=models.UniqueConstraint(
        fields={fields!r},
        name='{model_name}_unique_field1_field2',
    ),
)

Note: UniqueConstraint provides more features like:
- Conditional uniqueness (condition parameter)
- Partial indexes (expressions)
- Better introspection support
"""


class AddCheckConstraintRule(BaseRule):
    """Detect adding a check constraint that validates all rows.

    Adding a check constraint on a table with data requires
    PostgreSQL to validate ALL existing rows against the constraint.

    For large tables, this can take a long time and block writes.

    Safe pattern (PostgreSQL 12+):
    Add constraint as NOT VALID first, then validate separately.
    """

    rule_id = "SM017"
    severity = Severity.WARNING
    description = "Adding check constraint validates all existing rows"
    db_vendors = ["postgresql"]  # Most relevant for PostgreSQL

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a check constraint.

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

        # Check if it's a CheckConstraint
        constraint_class_name = type(constraint).__name__
        if constraint_class_name != "CheckConstraint":
            return None

        constraint_name = getattr(constraint, "name", "unknown")
        model_name = getattr(operation, "model_name", "unknown")

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding check constraint '{constraint_name}' on "
                f"'{model_name}' will validate all existing rows"
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        constraint = getattr(operation, "constraint", None)
        constraint_name = getattr(constraint, "name", "check_constraint")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for adding check constraint (PostgreSQL 12+):

1. Add constraint as NOT VALID (doesn't validate existing rows):
   migrations.RunSQL(
       sql='''
           ALTER TABLE {model_name}
           ADD CONSTRAINT {constraint_name}
           CHECK (your_condition)
           NOT VALID;
       ''',
       reverse_sql='ALTER TABLE {model_name} DROP CONSTRAINT {constraint_name};',
   ),

2. Validate in a separate migration (row-level lock only):
   migrations.RunSQL(
       sql='ALTER TABLE {model_name} VALIDATE CONSTRAINT {constraint_name};',
       reverse_sql=migrations.RunSQL.noop,
   ),

Note: VALIDATE CONSTRAINT takes a SHARE UPDATE EXCLUSIVE lock,
which allows reads and writes but blocks schema changes.
"""
