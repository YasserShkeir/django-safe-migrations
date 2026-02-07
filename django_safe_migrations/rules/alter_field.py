"""Rules for AlterField operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation

logger = logging.getLogger("django_safe_migrations")


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

    Safe changes (detected and skipped by this rule):
    - Adding null=True (removes NOT NULL constraint)
    - Changing only metadata (verbose_name, help_text, validators, etc.)
    - Adding or changing default values

    Safe pattern for unsafe changes:
    1. Add new column with desired type
    2. Backfill data in batches
    3. Update application to use new column
    4. Drop old column in later migration
    """

    rule_id = "SM004"
    severity = Severity.WARNING
    description = "Changing column type may rewrite table and lock it"

    # Attributes that are metadata-only and don't affect the database schema
    METADATA_ONLY_ATTRIBUTES = frozenset(
        {
            "verbose_name",
            "help_text",
            "error_messages",
            "validators",
            "choices",
            "editable",
            "serialize",
            "blank",
            "db_comment",
        }
    )

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
            **kwargs: Additional context (may include old_field).

        Returns:
            An Issue if the operation is potentially unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field
        field_type = field.__class__.__name__
        old_field = kwargs.get("old_field")

        # If we have the old field state, do precise comparison
        if old_field is not None:
            if self._is_safe_change_with_old_field(old_field, field):
                logger.debug(
                    "Skipping AlterField on %s.%s - safe change (old field known)",
                    operation.model_name,
                    operation.name,
                )
                return None
        else:
            # Fallback: use heuristics when old field is unavailable
            if self._is_likely_safe_change(field):
                logger.debug(
                    "Skipping AlterField on %s.%s - likely safe (heuristic)",
                    operation.model_name,
                    operation.name,
                )
                return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Altering field '{operation.name}' on '{operation.model_name}' "
                f"to type '{field_type}' may require table rewrite and lock"
            ),
        )

    def _is_safe_change_with_old_field(
        self, old_field: object, new_field: object
    ) -> bool:
        """Check if the change is safe by comparing old and new fields.

        Args:
            old_field: The field definition before this operation.
            new_field: The new field definition.

        Returns:
            True if the change is safe, False otherwise.
        """
        old_type = old_field.__class__.__name__
        new_type = new_field.__class__.__name__

        # Type change is potentially unsafe
        if old_type != new_type:
            return False

        # Same type — check if only metadata attributes changed
        for attr in self.METADATA_ONLY_ATTRIBUTES:
            old_val = getattr(old_field, attr, None)
            new_val = getattr(new_field, attr, None)
            if old_val != new_val:
                logger.debug(
                    "Metadata-only attribute '%s' changed: %s -> %s",
                    attr,
                    old_val,
                    new_val,
                )

        # Check if null changed (adding null=True is safe)
        old_null = getattr(old_field, "null", False)
        new_null = getattr(new_field, "null", False)
        if old_null != new_null and new_null:
            # Adding nullable — safe
            return True

        # Check if default changed (safe, metadata-only in PostgreSQL)
        from django.db.models.fields import NOT_PROVIDED

        old_default = getattr(old_field, "default", NOT_PROVIDED)
        new_default = getattr(new_field, "default", NOT_PROVIDED)
        if old_default != new_default and old_type == new_type:
            # Changing default on same type is safe (no schema change)
            # Check if anything else schema-affecting changed
            old_null = getattr(old_field, "null", False)
            new_null = getattr(new_field, "null", False)
            old_max = getattr(old_field, "max_length", None)
            new_max = getattr(new_field, "max_length", None)
            old_unique = getattr(old_field, "unique", False)
            new_unique = getattr(new_field, "unique", False)

            if old_null == new_null and old_max == new_max and old_unique == new_unique:
                return True

        # Same type, no schema-affecting change detected
        # Still check if there's a real schema change
        old_null = getattr(old_field, "null", False)
        new_null = getattr(new_field, "null", False)
        old_max = getattr(old_field, "max_length", None)
        new_max = getattr(new_field, "max_length", None)
        old_unique = getattr(old_field, "unique", False)
        new_unique = getattr(new_field, "unique", False)

        if (
            old_type == new_type
            and old_null == new_null
            and old_max == new_max
            and old_unique == new_unique
        ):
            # No schema-affecting attributes changed — metadata only
            return True

        return False

    def _is_likely_safe_change(self, field: object) -> bool:
        """Fallback heuristic when old field state is unavailable.

        Args:
            field: The new field definition.

        Returns:
            True if the change appears to be safe, False otherwise.
        """
        field_type = field.__class__.__name__

        # BooleanField/NullBooleanField alterations are usually safe
        if field_type in ("BooleanField", "NullBooleanField"):
            logger.debug("BooleanField alteration - likely safe")
            return True

        # TextField alterations are usually metadata-only
        if field_type == "TextField":
            logger.debug("TextField alteration - likely safe")
            return True

        # If null=True is set, the most common case is adding nullable (safe)
        if getattr(field, "null", False):
            logger.debug("Field has null=True - likely adding nullable")
            return True

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
            **kwargs: Additional context (may include old_field).

        Returns:
            An Issue if VARCHAR length is decreased, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # Only check CharField (which uses VARCHAR)
        if field_type != "CharField":
            return None

        new_max_length = getattr(field, "max_length", None)
        if new_max_length is None:
            return None

        old_field = kwargs.get("old_field")

        if old_field is not None:
            old_type = old_field.__class__.__name__
            old_max_length = getattr(old_field, "max_length", None)

            # Changing from non-CharField to CharField is a type change
            # (handled by SM004), not a length change
            if old_type != "CharField":
                return None

            # If old max_length is known, only warn on decrease
            if old_max_length is not None:
                if new_max_length >= old_max_length:
                    logger.debug(
                        "CharField max_length increased or unchanged "
                        "(%s -> %s) - safe",
                        old_max_length,
                        new_max_length,
                    )
                    return None

                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"Decreasing CharField '{operation.name}' max_length "
                        f"on '{operation.model_name}' from {old_max_length} "
                        f"to {new_max_length} requires table rewrite"
                    ),
                )

            # Old field was CharField but max_length unknown (shouldn't happen)
            # Fall through to generic warning

        # Fallback: old field unavailable, warn as potentially unsafe
        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Altering CharField '{operation.name}' on "
                f"'{operation.model_name}' - if decreasing max_length, "
                "this will rewrite the table"
            ),
        )

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


class AlterFieldNullFalseRule(BaseRule):
    """Detect AlterField changing null=True to null=False.

    When changing a field from nullable to NOT NULL, PostgreSQL must:
    1. Scan the entire table to verify no NULL values exist
    2. Add the NOT NULL constraint

    If any NULL values exist, the migration will fail. Even if no NULL values
    exist, the scan can take time on large tables.

    Safe pattern:
    1. Add a CHECK constraint as NOT VALID first
    2. Backfill any NULL values
    3. Validate the constraint
    4. Add the NOT NULL constraint
    """

    rule_id = "SM020"
    severity = Severity.ERROR
    description = "Changing field to NOT NULL may fail if NULL values exist"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation changes a field from NULL to NOT NULL.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include old_field).

        Returns:
            An Issue if the operation adds NOT NULL constraint, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field

        # Check if the field has null=False (the default)
        is_not_null = not getattr(field, "null", False)
        if not is_not_null:
            return None

        old_field = kwargs.get("old_field")

        if old_field is not None:
            # Only warn if the field was previously nullable
            was_nullable = getattr(old_field, "null", False)
            if not was_nullable:
                # Field was already NOT NULL — this isn't adding a constraint
                logger.debug(
                    "Field %s.%s was already NOT NULL, skipping SM020",
                    operation.model_name,
                    operation.name,
                )
                return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"AlterField on '{operation.name}' sets null=False. "
                f"Ensure all existing rows in '{operation.model_name}' "
                "have non-NULL values, or the migration will fail."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely adding NOT NULL constraint.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        # Documentation text showing SQL patterns, not executed
        return f"""Safe pattern for adding NOT NULL constraint:

1. First, check if any NULL values exist:
   SELECT COUNT(*) FROM app_{model_name}
   WHERE {field_name} IS NULL;

2. If NULL values exist, backfill them first:
   UPDATE app_{model_name}
   SET {field_name} = 'default_value' WHERE {field_name} IS NULL;

3. On PostgreSQL, you can add NOT NULL more safely:
   ALTER TABLE app_{model_name}
   ADD CONSTRAINT {field_name}_not_null
   CHECK ({field_name} IS NOT NULL) NOT VALID;

   ALTER TABLE app_{model_name}
   VALIDATE CONSTRAINT {field_name}_not_null;

   ALTER TABLE app_{model_name}
   ALTER COLUMN {field_name} SET NOT NULL;

   ALTER TABLE app_{model_name}
   DROP CONSTRAINT {field_name}_not_null;

This allows the validation to happen without blocking writes.
"""  # nosec B608  # noqa: E501


class AlterFieldUniqueRule(BaseRule):
    """Detect adding unique constraint via AlterField(unique=True).

    Adding unique=True via AlterField causes PostgreSQL to:
    1. Scan the entire table to check for duplicates
    2. Create a unique index
    3. Hold locks during the operation

    This can be slow and block writes on large tables.

    Safe pattern:
    1. Create a unique index concurrently first
    2. Then add the constraint using the existing index
    """

    rule_id = "SM021"
    severity = Severity.ERROR
    description = "Adding unique=True via AlterField locks table during index creation"
    db_vendors = ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds unique constraint via AlterField.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include old_field).

        Returns:
            An Issue if unique=True is being added, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field

        # Check if unique=True is set
        is_unique = getattr(field, "unique", False)
        if not is_unique:
            return None

        old_field = kwargs.get("old_field")

        if old_field is not None:
            # Only warn if the field was not already unique
            was_unique = getattr(old_field, "unique", False)
            if was_unique:
                logger.debug(
                    "Field %s.%s was already unique, skipping SM021",
                    operation.model_name,
                    operation.name,
                )
                return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding unique=True to '{operation.name}' on "
                f"'{operation.model_name}' via AlterField will scan and lock "
                "the entire table during index creation."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safely adding unique constraint.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for adding unique constraint (PostgreSQL):

1. Create the unique index concurrently first:
   from django.contrib.postgres.operations import AddIndexConcurrently

   class Migration(migrations.Migration):
       atomic = False  # Required for concurrent operations

       operations = [
           AddIndexConcurrently(
               model_name='{model_name}',
               index=models.Index(
                   fields=['{field_name}'],
                   name='{model_name}_{field_name}_uniq_idx',
               ),
           ),
       ]

2. Then add the constraint using the existing index:
   migrations.RunSQL(
       sql='ALTER TABLE app_{model_name} '
           'ADD CONSTRAINT {model_name}_{field_name}_uniq '
           'UNIQUE USING INDEX {model_name}_{field_name}_uniq_idx',
       reverse_sql='ALTER TABLE app_{model_name} '
           'DROP CONSTRAINT {model_name}_{field_name}_uniq',
   )

This allows index creation to happen without blocking reads/writes.
"""  # noqa: E501


class DropNotNullRule(BaseRule):
    """Detect AlterField changing null=False to null=True (dropping NOT NULL).

    While dropping NOT NULL is generally safe from a locking perspective,
    it can indicate an unintentional data model regression. Allowing NULL
    values where they weren't allowed before can lead to:
    - Application code that doesn't handle NULL values
    - Data integrity issues
    - Unexpected query results with NULL comparisons

    This rule emits a WARNING to ensure the change is intentional.
    """

    rule_id = "SM029"
    severity = Severity.WARNING
    description = "Dropping NOT NULL constraint may allow unintended NULL values"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation changes a field from NOT NULL to nullable.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include old_field).

        Returns:
            An Issue if NOT NULL is being dropped, None otherwise.
        """
        if not isinstance(operation, migrations.AlterField):
            return None

        field = operation.field

        # Check if the new field is nullable
        is_nullable = getattr(field, "null", False)
        if not is_nullable:
            return None

        old_field = kwargs.get("old_field")

        if old_field is not None:
            # Only warn if the field was previously NOT NULL
            was_not_null = not getattr(old_field, "null", False)
            if not was_not_null:
                # Field was already nullable — no change
                logger.debug(
                    "Field %s.%s was already nullable, skipping SM029",
                    operation.model_name,
                    operation.name,
                )
                return None
        else:
            # Without old field info, we can't tell if this is a change
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"AlterField on '{operation.name}' changes "
                f"'{operation.model_name}' from NOT NULL to nullable. "
                "Ensure application code handles NULL values correctly."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for dropping NOT NULL safely.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Before dropping NOT NULL on '{field_name}':

1. Verify application code handles NULL values:
   - Check all queries filtering on this field
   - Check template/serializer access to this field
   - Check any aggregations (NULL values are excluded from COUNT, etc.)

2. Consider if a default value would be better:
   migrations.AlterField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.FieldType(default='some_value'),
   )

3. If intentional, suppress this warning:
   migrations.AlterField(  # safe-migrations: ignore SM029
       ...
   )
"""
