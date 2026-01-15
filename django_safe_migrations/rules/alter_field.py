"""Rules for AlterField operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class AlterColumnTypeRule(BaseRule):
    """Detect changing column type which may rewrite the table.

    Changing a column's type often requires PostgreSQL to rewrite the
    entire table, which takes an ACCESS EXCLUSIVE lock and blocks all
    reads and writes. Some type changes are safe (e.g., varchar(50) to
    varchar(100)), but many are not.

    Dangerous type changes:
    - Numeric to text (or vice versa)
    - Changing precision/scale of numeric types
    - Changing between incompatible types

    Safe pattern:
    1. Add new column with desired type
    2. Backfill data in batches
    3. Update application to use new column
    4. Drop old column in later migration
    """

    rule_id = "SM004"
    severity = Severity.WARNING
    description = "Changing column type may rewrite table and lock it"

    # Type changes that are generally safe
    SAFE_TYPE_CHANGES: set[tuple[str, str]] = {
        # Widening varchar is safe in PostgreSQL
        ("CharField", "CharField"),
        ("TextField", "TextField"),
        # Adding null to existing field
    }

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation alters a column type unsafely.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation is potentially unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # We can't easily detect the old type from the operation alone,
        # so we warn about all AlterField operations that change the field
        # type significantly.

        # Skip if just changing null/blank/default (metadata changes)
        # These are generally safe
        if self._is_metadata_only_change(field):
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Altering field '{operation.name}' on '{operation.model_name}' "
                f"to type '{field_type}' may require table rewrite and lock"
            ),
        )

    def _is_metadata_only_change(self, field: object) -> bool:
        """Check if field change appears to be metadata-only.

        This is a heuristic - we can't know the previous field definition.
        We assume if the field has very common safe attributes set, it
        might be a safe change.

        Args:
            field: The new field definition.

        Returns:
            True if the change appears to be metadata-only.
        """
        # For now, we flag all AlterField operations as potentially unsafe
        # In the future, we could track state between migrations
        return False

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely changing column type.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for changing column type (expand/contract):

1. Migration 1 - Add new column with desired type:
   migrations.AddField(
       model_name='{model_name}',
       name='{field_name}_new',
       field=models.NewFieldType(..., null=True),
   )

2. Data migration - Copy and transform data in batches:
   for batch in Model.objects.iterator(chunk_size=1000):
       batch.{field_name}_new = transform(batch.{field_name})
       batch.save(update_fields=['{field_name}_new'])

3. Update application code to read from both, write to both

4. Migration 3 - Drop old column and rename new:
   migrations.RemoveField(model_name='{model_name}', name='{field_name}')
   migrations.RenameField(
       model_name='{model_name}',
       old_name='{field_name}_new',
       new_name='{field_name}',
   )
"""


class AddForeignKeyValidatesRule(BaseRule):
    """Detect adding FK constraint that validates existing rows.

    When you add a ForeignKey or create a constraint, PostgreSQL will
    validate that all existing rows satisfy the constraint. This
    requires scanning the entire table and can take a long time on
    large tables while holding locks.

    Safe pattern:
    1. Add the FK with db_constraint=False initially
    2. Create the constraint as NOT VALID
    3. Validate the constraint in a separate transaction
    """

    rule_id = "SM005"
    severity = Severity.WARNING
    description = "Adding foreign key validates existing rows (may lock table)"
    db_vendors = ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a validating foreign key.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation is potentially unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # Check if it's a ForeignKey or OneToOneField
        if field_type not in ("ForeignKey", "OneToOneField"):
            return None

        # Check if db_constraint is True (default)
        has_constraint = getattr(field, "db_constraint", True)

        if not has_constraint:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding ForeignKey '{operation.name}' to '{operation.model_name}' "
                "will validate all existing rows, potentially locking the table"
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely adding foreign key.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for adding ForeignKey without table lock:

1. Add FK without database constraint first:
   migrations.AddField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.ForeignKey(
           to='related_model',
           on_delete=models.CASCADE,
           db_constraint=False,  # No DB-level constraint yet
           null=True,
       ),
   )

2. Backfill data if needed

3. Add constraint as NOT VALID using RunSQL:
   migrations.RunSQL(
       sql='ALTER TABLE app_{model_name} ADD CONSTRAINT ... NOT VALID',
       reverse_sql='ALTER TABLE app_{model_name} DROP CONSTRAINT ...',
   )

4. Validate constraint in separate migration (can run concurrently):
   migrations.RunSQL(
       sql='ALTER TABLE app_{model_name} VALIDATE CONSTRAINT ...',
       reverse_sql=migrations.RunSQL.noop,
   )
"""


class RenameColumnRule(BaseRule):
    """Detect column rename which may break old code.

    Renaming a column is instant in the database, but if old application
    code is still running (during deployment), it will fail when trying
    to access the old column name.

    Safe pattern:
    1. Add new column (copy of old)
    2. Update code to write to both columns
    3. Deploy code that reads from new column
    4. Drop old column
    """

    rule_id = "SM006"
    severity = Severity.INFO
    description = "Column rename may break code during deployment"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation renames a column.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation renames a column, None otherwise.
        """
        if not isinstance(operation, migrations.RenameField):
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Renaming field '{operation.old_name}' to '{operation.new_name}' "
                f"on '{operation.model_name}' may break old code during deployment"
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely renaming column.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        old_name = getattr(operation, "old_name", "old_field")
        new_name = getattr(operation, "new_name", "new_field")
        model_name = getattr(operation, "model_name", "model")

        # Build data migration example (suggestion string, not executed)
        data_migration = (
            f"UPDATE app_{model_name} SET {new_name} = {old_name};"  # nosec B608
        )

        return f"""Safe pattern for renaming columns (zero-downtime):

Option A: If you can tolerate brief downtime, RenameField is fine.

Option B: Zero-downtime approach (expand/contract):

1. Migration 1 - Add new column:
   migrations.AddField(
       model_name='{model_name}',
       name='{new_name}',
       field=models.SameFieldType(null=True),
   )

2. Data migration - Copy data:
   {data_migration}

3. Deploy code that writes to BOTH columns, reads from new

4. Migration 2 - Make new column NOT NULL (if needed)

5. Deploy code that only reads/writes new column

6. Migration 3 - Drop old column:
   migrations.RemoveField(model_name='{model_name}', name='{old_name}')
"""


class AlterVarcharLengthRule(BaseRule):
    """Detect decreasing VARCHAR length which rewrites the table.

    In PostgreSQL:
    - Increasing VARCHAR length is a metadata-only change (safe)
    - Decreasing VARCHAR length requires table rewrite (unsafe)
    - Changing from VARCHAR to TEXT is safe
    - Changing from TEXT to VARCHAR requires rewrite

    Safe patterns:
    - Use TEXT instead of VARCHAR when possible (no length limit)
    - Only increase VARCHAR length, never decrease
    """

    rule_id = "SM013"
    severity = Severity.WARNING
    description = "Decreasing VARCHAR length requires table rewrite"
    db_vendors = ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation decreases VARCHAR length.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if VARCHAR length might be decreased, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # Only check CharField (which uses VARCHAR)
        if field_type != "CharField":
            return None

        # We can't know the old max_length from the operation alone
        # So we warn about AlterField on CharField as potentially unsafe
        max_length = getattr(field, "max_length", None)

        if max_length is not None:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"Altering CharField '{operation.name}' on "
                    f"'{operation.model_name}' - if decreasing max_length, "
                    "this will rewrite the table"
                ),
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for altering VARCHAR safely.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")

        # Build SQL examples (suggestion strings, not executed)
        verify_sql = f"SELECT MAX(LENGTH({field_name})) FROM table;"  # nosec B608
        check_sql = f"CHECK (LENGTH({field_name}) <= 50)"  # nosec B608

        return f"""VARCHAR length changes in PostgreSQL:

SAFE operations (metadata only, no table lock):
- Increasing max_length: CharField(max_length=50) → CharField(max_length=100)
- Changing to unlimited: CharField → TextField

UNSAFE operations (requires table rewrite):
- Decreasing max_length: CharField(max_length=100) → CharField(max_length=50)
- Changing from TEXT to VARCHAR

If you need to decrease length:
1. Verify all existing data fits in new length:
   {verify_sql}

2. Consider using CHECK constraint instead:
   migrations.RunSQL(
       sql='ALTER TABLE table ADD CONSTRAINT check_len '
           '{check_sql}',
       reverse_sql='ALTER TABLE table DROP CONSTRAINT check_len',
   )

3. Or use the expand/contract pattern with a new column.
"""


class RenameModelRule(BaseRule):
    """Detect RenameModel operations that may break foreign keys.

    Renaming a model renames the database table, which can cause issues:
    1. Foreign keys from other apps may reference the old table name
    2. Raw SQL queries using the table name will break
    3. Database-level permissions may be lost
    4. Indexes and constraints may need renaming

    Safe pattern:
    Use db_table Meta option to keep the old table name, or:
    1. Create new model with new name
    2. Copy data
    3. Update foreign keys
    4. Remove old model
    """

    rule_id = "SM014"
    severity = Severity.WARNING
    description = "Renaming model may break foreign keys and references"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation renames a model.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation renames a model, None otherwise.
        """
        if not isinstance(operation, migrations.RenameModel):
            return None

        old_name = getattr(operation, "old_name", "unknown")
        new_name = getattr(operation, "new_name", "unknown")

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Renaming model '{old_name}' to '{new_name}' "
                f"may break foreign keys and external references"
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely renaming a model.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        old_name = getattr(operation, "old_name", "OldModel")
        new_name = getattr(operation, "new_name", "NewModel")
        old_table = old_name.lower()

        return f"""Safe patterns for renaming a model:

Option 1: Keep the old table name (safest)
------------------------------------------
Rename the model class but keep the database table:

class {new_name}(models.Model):
    # ... fields ...

    class Meta:
        db_table = '{old_table}'  # Keep the old table name

This avoids any database changes while updating your code.


Option 2: Gradual migration (for complex cases)
-----------------------------------------------
1. Create a new model with the new name
2. Add a data migration to copy data
3. Update all foreign keys and references
4. Remove the old model in a later migration


Option 3: Proceed with rename (if you're certain)
------------------------------------------------
If you're sure no external references exist:
1. Audit all raw SQL queries for table name references
2. Check for database-level permissions on the table
3. Verify no other apps have foreign keys to this model
4. Update any db_constraint=False foreign keys manually
"""
