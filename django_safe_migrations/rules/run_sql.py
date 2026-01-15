"""Rules for RunSQL and RunPython operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class RunSQLWithoutReverseRule(BaseRule):
    """Detect RunSQL without reverse_sql defined.

    RunSQL operations without reverse_sql cannot be reversed, which
    makes it impossible to roll back the migration if something goes
    wrong. This is especially dangerous in production.

    Safe pattern:
    Always provide reverse_sql, even if it's migrations.RunSQL.noop
    for operations that don't need reversal (like adding comments).
    """

    rule_id = "SM007"
    severity = Severity.WARNING
    description = "RunSQL without reverse_sql cannot be rolled back"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if RunSQL operation has reverse_sql.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if reverse_sql is missing, None otherwise.
        """
        if not isinstance(operation, migrations.RunSQL):
            return None

        # Check if reverse_sql is None or empty
        reverse_sql = getattr(operation, "reverse_sql", None)

        if reverse_sql is None:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message="RunSQL operation has no reverse_sql - cannot be rolled back",
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for adding reverse_sql.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """Always provide reverse_sql for RunSQL operations:

# If the operation has a logical reverse:
migrations.RunSQL(
    sql='CREATE INDEX CONCURRENTLY idx ON table (column)',
    reverse_sql='DROP INDEX CONCURRENTLY IF EXISTS idx',
)

# If the operation doesn't need reversal (e.g., adding comment):
migrations.RunSQL(
    sql="COMMENT ON TABLE users IS 'Main users table'",
    reverse_sql=migrations.RunSQL.noop,
)

# For complex cases, use state_operations to keep Django in sync:
migrations.RunSQL(
    sql='...',
    reverse_sql='...',
    state_operations=[
        migrations.AddField(...),  # Tells Django about the schema change
    ],
)
"""


class EnumAddValueInTransactionRule(BaseRule):
    """Detect adding enum values inside a transaction.

    In PostgreSQL, ALTER TYPE ... ADD VALUE cannot run inside a
    transaction block. Django migrations run in transactions by default,
    so this will fail with:
    "ALTER TYPE ... ADD cannot run inside a transaction block"

    Safe pattern:
    Use atomic=False on the migration class, or use a separate
    migration that creates the enum value.
    """

    rule_id = "SM012"
    severity = Severity.ERROR
    description = "Adding enum value in transaction will fail in PostgreSQL"
    db_vendors = ["postgresql"]

    # Patterns that indicate adding enum value
    ENUM_ADD_PATTERNS = [
        r"ALTER\s+TYPE\s+\w+\s+ADD\s+VALUE",
        r"add\s+value",
    ]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if RunSQL adds enum value in a transaction.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if enum value is added in transaction, None otherwise.
        """
        if not isinstance(operation, migrations.RunSQL):
            return None

        # Get the SQL string(s)
        sql = getattr(operation, "sql", "")

        # Handle case where sql is a list of statements
        if isinstance(sql, (list, tuple)):
            sql = " ".join(str(s) for s in sql)
        else:
            sql = str(sql)

        # Check if SQL contains enum value addition
        sql_lower = sql.lower()
        for pattern in self.ENUM_ADD_PATTERNS:
            if re.search(pattern, sql_lower, re.IGNORECASE):
                # Check if migration is atomic (default is True)
                is_atomic = getattr(migration, "atomic", True)

                if is_atomic:
                    return self.create_issue(
                        operation=operation,
                        migration=migration,
                        message=(
                            "ALTER TYPE ADD VALUE cannot run inside a transaction. "
                            "Set atomic=False on the Migration class."
                        ),
                    )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for adding enum values safely.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """To add enum values in PostgreSQL, disable transaction wrapping:

class Migration(migrations.Migration):
    atomic = False  # Required for ALTER TYPE ADD VALUE

    dependencies = [...]

    operations = [
        migrations.RunSQL(
            sql="ALTER TYPE my_enum ADD VALUE 'new_value'",
            reverse_sql=migrations.RunSQL.noop,  # Can't remove enum values
        ),
    ]

Note: You cannot remove enum values in PostgreSQL. The reverse_sql
should be RunSQL.noop. To "remove" a value, you'd need to recreate
the entire enum type.

Alternative: Use a text field with CHECK constraint instead of enum
for more flexibility.
"""


class LargeDataMigrationRule(BaseRule):
    """Detect RunPython that might process large amounts of data.

    Data migrations using RunPython can be slow and block deployments
    if they process too much data in a single transaction. They can
    also cause lock contention.

    Safe pattern:
    - Process data in batches
    - Use iterator() to avoid loading all rows into memory
    - Consider running data migrations outside of the deployment
    """

    rule_id = "SM008"
    severity = Severity.INFO
    description = "Data migration may be slow on large tables"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation is a RunPython data migration.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue for all RunPython operations, None otherwise.
        """
        if not isinstance(operation, migrations.RunPython):
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                "RunPython data migration may be slow on large tables. "
                "Consider batching and using iterator()."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for handling large data migrations.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """Best practices for data migrations:

1. Process in batches to avoid long transactions:

def migrate_data(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    batch_size = 1000

    while True:
        batch = list(Model.objects.filter(
            new_field__isnull=True
        )[:batch_size])

        if not batch:
            break

        for obj in batch:
            obj.new_field = compute_value(obj.old_field)

        Model.objects.bulk_update(batch, ['new_field'])

2. Use iterator() to avoid loading all rows into memory:

for obj in Model.objects.iterator(chunk_size=1000):
    ...

3. For very large tables, consider running data migrations
   separately from schema migrations, possibly using a
   management command or background job.

4. Mark data migrations as elidable if they're not required
   for fresh database setup:

migrations.RunPython(
    migrate_data,
    reverse_code=migrations.RunPython.noop,
    elidable=True,
)
"""


class RunPythonWithoutReverseRule(BaseRule):
    """Detect RunPython without reverse_code defined.

    RunPython operations without reverse_code cannot be reversed,
    which makes it impossible to roll back the migration if something
    goes wrong. This is especially dangerous in production.

    Safe pattern:
    Always provide reverse_code, even if it's migrations.RunPython.noop
    for operations that don't need reversal.
    """

    rule_id = "SM016"
    severity = Severity.INFO
    description = "RunPython without reverse_code cannot be rolled back"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if RunPython operation has reverse_code.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if reverse_code is missing, None otherwise.
        """
        if not isinstance(operation, migrations.RunPython):
            return None

        # Check if reverse_code is None
        reverse_code = getattr(operation, "reverse_code", None)

        if reverse_code is None:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    "RunPython operation has no reverse_code - " "cannot be rolled back"
                ),
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for adding reverse_code.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """Always provide reverse_code for RunPython operations:

# If the operation has a logical reverse:
def forward_migration(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    Model.objects.filter(field='old').update(field='new')

def reverse_migration(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    Model.objects.filter(field='new').update(field='old')

migrations.RunPython(
    forward_migration,
    reverse_code=reverse_migration,
)

# If the operation doesn't need reversal:
migrations.RunPython(
    populate_defaults,
    reverse_code=migrations.RunPython.noop,
)

# If the reverse is complex, consider documenting it:
def complex_reverse(apps, schema_editor):
    raise NotImplementedError("Manually reverse this migration")

migrations.RunPython(
    forward_migration,
    reverse_code=complex_reverse,
)
"""
