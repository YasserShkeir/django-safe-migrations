"""Rules for relationship field operations (ForeignKey, ManyToMany, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class AddManyToManyRule(BaseRule):
    """Detect adding ManyToManyField which creates a junction table.

    Adding a ManyToManyField creates a new junction table in the database.
    This is generally safe but worth noting because:
    1. It creates a new table (schema change)
    2. The table may need indexing for performance
    3. Consider using through= for custom junction tables

    This is an INFO-level rule for awareness.
    """

    rule_id = "SM023"
    severity = Severity.INFO
    description = "Adding ManyToManyField creates a new junction table"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a ManyToManyField.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if a ManyToMany field is being added, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        if field_type != "ManyToManyField":
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding ManyToManyField '{operation.name}' to "
                f"'{operation.model_name}'. "
                "This creates a new junction table."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return information about ManyToMany fields.

        Args:
            operation: The operation.

        Returns:
            A multi-line string with information about the operation.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""ManyToManyField creates a junction table:

The junction table will be named: app_{model_name}_{field_name}

Considerations:
1. The junction table is created empty (safe operation)
2. Django creates indexes on both foreign keys by default
3. For additional fields on the relationship, use a custom through model:

   class Membership(models.Model):
       person = models.ForeignKey(Person, on_delete=models.CASCADE)
       group = models.ForeignKey(Group, on_delete=models.CASCADE)
       date_joined = models.DateField()

   class Person(models.Model):
       groups = models.ManyToManyField(Group, through='Membership')

4. For very large tables, consider if the junction table needs
   additional indexes for your query patterns.
"""


class ForeignKeyWithoutIndexRule(BaseRule):
    """Detect ForeignKey with db_index=False.

    By default, Django creates an index on ForeignKey fields (db_index=True).
    If db_index=False is explicitly set, queries filtering by this foreign
    key will be slow on large tables.

    This is usually an oversight - most foreign keys benefit from an index.
    """

    rule_id = "SM025"
    severity = Severity.WARNING
    description = "ForeignKey with db_index=False may cause slow queries"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a ForeignKey without an index.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if FK has db_index=False, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # Only check ForeignKey and OneToOneField
        if field_type not in ("ForeignKey", "OneToOneField"):
            return None

        # ForeignKey has db_index=True by default
        # OneToOneField creates a unique constraint (which implies an index)
        # Only warn if db_index is explicitly False
        db_index = getattr(field, "db_index", True)

        if db_index is False:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"Adding {field_type} '{operation.name}' on "
                    f"'{operation.model_name}' with db_index=False. "
                    "Queries filtering by this field will not use an index."
                ),
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for ForeignKey indexing.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested fix.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""ForeignKey without db_index:

Unless you're certain this foreign key is never used in queries,
consider enabling the index:

    migrations.AddField(
        model_name='{model_name}',
        name='{field_name}',
        field=models.ForeignKey(
            to='related_model',
            on_delete=models.CASCADE,
            db_index=True,  # Default - creates an index
        ),
    )

Reasons to disable db_index:
- The table is very small and won't benefit from indexes
- You have a custom composite index that includes this column
- Write performance is critical and reads are rare

If you intentionally set db_index=False, you can suppress this warning:
    # safe-migrations: ignore SM025
"""
