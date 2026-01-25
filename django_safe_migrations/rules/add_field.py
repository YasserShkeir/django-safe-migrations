"""Rules for AddField operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class NotNullWithoutDefaultRule(BaseRule):
    """Detect adding NOT NULL column without a default value.

    Adding a NOT NULL column without a default requires PostgreSQL to:
    1. Take an ACCESS EXCLUSIVE lock on the table
    2. Rewrite the entire table to add the column with NULL checks

    This blocks all reads and writes and can take a long time on large tables.

    Safe pattern:
    1. Add the column as nullable
    2. Backfill existing rows in batches
    3. Add the NOT NULL constraint in a separate migration
    """

    rule_id = "SM001"
    severity = Severity.ERROR
    description = "Adding NOT NULL column without default will lock table"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a NOT NULL field without default.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation is unsafe, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field

        # Check if field is NOT NULL (null=False is default)
        is_not_null = not getattr(field, "null", False)

        # Check if field has a default - Django uses NOT_PROVIDED sentinel
        from django.db.models.fields import NOT_PROVIDED

        default_value = getattr(field, "default", NOT_PROVIDED)
        has_default = default_value is not NOT_PROVIDED

        # Also check has_default() method if available
        if not has_default and hasattr(field, "has_default"):
            has_default = field.has_default()

        # Primary keys and auto fields are OK
        is_auto = getattr(field, "primary_key", False) or field.__class__.__name__ in (
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
            "UUIDField",  # with default=uuid.uuid4
        )

        # OneToOneField and ForeignKey with db_constraint=False are special
        is_relation_no_constraint = hasattr(field, "db_constraint") and not getattr(
            field, "db_constraint", True
        )

        if (
            is_not_null
            and not has_default
            and not is_auto
            and not is_relation_no_constraint
        ):
            model_name = getattr(operation, "model_name", "unknown")
            field_name = getattr(operation, "name", "unknown")

            return self.create_issue(
                operation=operation,
                message=(
                    f"Adding NOT NULL field '{field_name}' to '{model_name}' "
                    f"without a default value will lock the table"
                ),
                migration=migration,
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return the suggested fix for this operation.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for adding NOT NULL field:

1. Migration 1 - Add field as nullable:
   migrations.AddField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.CharField(max_length=255, null=True),
   )

2. Data migration - Backfill existing rows in batches:
   def backfill_{field_name}(apps, schema_editor):
       Model = apps.get_model('yourapp', '{model_name.title()}')
       batch_size = 1000
       while Model.objects.filter({field_name}__isnull=True).exists():
           ids = list(Model.objects.filter({field_name}__isnull=True)
                      .values_list('id', flat=True)[:batch_size])
           Model.objects.filter(id__in=ids).update({field_name}='default_value')

3. Migration 3 - Add NOT NULL constraint:
   migrations.AlterField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.CharField(max_length=255, null=False),
   )
"""


class ExpensiveDefaultCallableRule(BaseRule):
    """Detect AddField with potentially expensive callable default.

    When adding a field with a callable default (like timezone.now or
    datetime.now), the callable is executed for each existing row during
    the migration. This can be slow on large tables.

    Note: uuid.uuid4 is fast and whitelisted.

    Safe patterns:
    - Use a static default value if possible
    - Add field as nullable first, then backfill in batches
    - For timestamps, consider using db_default with NOW() (Django 5.0+)
    """

    rule_id = "SM022"
    severity = Severity.WARNING
    description = "Callable default may be slow for large table backfills"

    # Callables that are known to be fast
    FAST_CALLABLES = frozenset(
        {
            "uuid4",
            "uuid.uuid4",
        }
    )

    # Callables that are known to be potentially slow when called per-row
    SLOW_CALLABLES = frozenset(
        {
            "now",
            "datetime.now",
            "datetime.datetime.now",
            "timezone.now",
            "django.utils.timezone.now",
            "date.today",
            "datetime.date.today",
        }
    )

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation has a potentially expensive callable default.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the default callable may be slow, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field

        # Check if field has a default
        from django.db.models.fields import NOT_PROVIDED

        default_value = getattr(field, "default", NOT_PROVIDED)

        if default_value is NOT_PROVIDED:
            return None

        # Check if it's a callable
        if not callable(default_value):
            return None

        # Get the callable's name for checking
        callable_name = getattr(default_value, "__name__", "")
        callable_module = getattr(default_value, "__module__", "")
        full_name = (
            f"{callable_module}.{callable_name}" if callable_module else callable_name
        )

        # Skip if it's a known fast callable
        if callable_name in self.FAST_CALLABLES or full_name in self.FAST_CALLABLES:
            return None

        # Check if it's a known slow callable
        is_slow = (
            callable_name in self.SLOW_CALLABLES
            or full_name in self.SLOW_CALLABLES
            or any(slow in full_name for slow in self.SLOW_CALLABLES)
        )

        if is_slow:
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"AddField '{operation.name}' on '{operation.model_name}' uses "
                    f"callable default '{callable_name}'. This will be called for "
                    "each existing row, which may be slow on large tables."
                ),
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for handling callable defaults.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe patterns for callable defaults:

Option 1: Use database-level default (Django 5.0+)
--------------------------------------------------
Use db_default instead of default for database-computed values:

    from django.db.models.functions import Now

    migrations.AddField(
        model_name='{model_name}',
        name='{field_name}',
        field=models.DateTimeField(db_default=Now()),
    )

Option 2: Add nullable first, then backfill
-------------------------------------------
1. Add field as nullable with no default:
   migrations.AddField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.DateTimeField(null=True),
   )

2. Backfill in batches:
   def backfill(apps, schema_editor):
       Model = apps.get_model('app', '{model_name}')
       from django.utils import timezone
       Model.objects.filter({field_name}__isnull=True).update(
           {field_name}=timezone.now()
       )

3. Add NOT NULL constraint:
   migrations.AlterField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.DateTimeField(null=False, default=timezone.now),
   )

Option 3: Use a static default
------------------------------
If exact timestamp isn't required, use a static value:

    migrations.AddField(
        model_name='{model_name}',
        name='{field_name}',
        field=models.DateTimeField(default=datetime.datetime(2024, 1, 1)),
    )
"""
