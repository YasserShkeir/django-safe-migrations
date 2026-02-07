"""Rules for AddField operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation

logger = logging.getLogger("django_safe_migrations")


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

        # Check for db_default (Django 5.0+)
        db_default = getattr(field, "db_default", None)
        if db_default is not None:
            # db_default uses a sentinel NOT_PROVIDED value in Django 5.0+
            try:
                from django.db.models.fields import NOT_PROVIDED as DB_NOT_PROVIDED

                if db_default is not DB_NOT_PROVIDED:
                    has_default = True
            except ImportError:
                # Pre-Django 5.0, db_default doesn't exist
                has_default = True

        # Primary keys and auto fields are OK
        is_auto = getattr(field, "primary_key", False) or field.__class__.__name__ in (
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
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

        # Check if it's a known slow callable (exact match only)
        is_slow = (
            callable_name in self.SLOW_CALLABLES or full_name in self.SLOW_CALLABLES
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


class PreferBigIntRule(BaseRule):
    """Detect AutoField or IntegerField used as primary key.

    32-bit integer primary keys (AutoField, IntegerField with primary_key=True)
    can overflow at ~2.1 billion rows. For new tables, BigAutoField or
    BigIntegerField should be preferred to avoid costly future migrations.

    Safe pattern:
    Use BigAutoField or BigIntegerField for primary keys, or set
    DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' in settings.
    """

    rule_id = "SM028"
    severity = Severity.WARNING
    description = "Prefer BigAutoField/BigIntegerField over 32-bit primary keys"

    # 32-bit auto/int field types that may overflow
    SMALL_PK_TYPES = frozenset(
        {
            "AutoField",
            "SmallAutoField",
        }
    )

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation uses a 32-bit integer primary key.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if a small PK type is used, None otherwise.
        """
        # Check AddField with primary_key=True
        if isinstance(operation, migrations.AddField):
            field = operation.field
            field_type = field.__class__.__name__
            is_pk = getattr(field, "primary_key", False)

            if is_pk and field_type in self.SMALL_PK_TYPES:
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"Field '{operation.name}' on '{operation.model_name}' "
                        f"uses {field_type} as primary key. Consider using "
                        "BigAutoField to avoid overflow at ~2.1 billion rows."
                    ),
                )

        # Check CreateModel for pk fields in the fields list
        if isinstance(operation, migrations.CreateModel):
            model_name = getattr(operation, "name", "unknown")
            fields = getattr(operation, "fields", [])
            for field_name, field in fields:
                field_type = field.__class__.__name__
                is_pk = getattr(field, "primary_key", False)
                if is_pk and field_type in self.SMALL_PK_TYPES:
                    return self.create_issue(
                        operation=operation,
                        migration=migration,
                        message=(
                            f"Field '{field_name}' on '{model_name}' uses "
                            f"{field_type} as primary key. Consider using "
                            "BigAutoField to avoid overflow at ~2.1 billion rows."
                        ),
                    )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for using BigAutoField.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """Use BigAutoField instead of AutoField for primary keys:

1. In your model:
   class MyModel(models.Model):
       id = models.BigAutoField(primary_key=True)

2. Or set the project-wide default in settings.py:
   DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

BigAutoField uses 64-bit integers, supporting up to ~9.2 quintillion rows.
"""


class PreferTextOverVarcharRule(BaseRule):
    """Detect CharField (VARCHAR) usage on PostgreSQL.

    In PostgreSQL, there is no performance difference between VARCHAR(N)
    and TEXT. Using TEXT avoids future migrations to increase max_length.

    This is an informational rule specific to PostgreSQL.
    """

    rule_id = "SM031"
    severity = Severity.INFO
    description = "Consider using TextField instead of CharField on PostgreSQL"
    db_vendors = ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if AddField uses CharField on PostgreSQL.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if CharField is used, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        if field_type != "CharField":
            return None

        # Skip if max_length is small (likely intentional, e.g. status codes)
        max_length = getattr(field, "max_length", None)
        if max_length is not None and max_length <= 32:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Field '{operation.name}' on '{operation.model_name}' uses "
                f"CharField(max_length={max_length}). On PostgreSQL, TextField "
                "has identical performance and avoids length-change migrations."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for using TextField.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """On PostgreSQL, TEXT and VARCHAR(N) have identical performance.

Consider using TextField instead of CharField:

    # Instead of:
    field = models.CharField(max_length=255)

    # Use:
    field = models.TextField()

    # If you need length validation, use MaxLengthValidator:
    from django.core.validators import MaxLengthValidator
    field = models.TextField(validators=[MaxLengthValidator(255)])

This avoids future migrations when max_length needs to increase.
"""


class PreferTimestampTZRule(BaseRule):
    """Detect DateTimeField when USE_TZ is False.

    When USE_TZ is False, Django stores naive datetimes. This can
    cause issues with daylight saving time transitions and makes
    it harder to support multiple timezones later.

    This is an informational rule to encourage timezone-aware datetimes.
    """

    rule_id = "SM032"
    severity = Severity.INFO
    description = "DateTimeField with USE_TZ=False stores naive datetimes"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if DateTimeField is added when USE_TZ is False.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if USE_TZ is False, None otherwise.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        if field_type != "DateTimeField":
            return None

        from django.conf import settings

        if getattr(settings, "USE_TZ", True):
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"DateTimeField '{operation.name}' on '{operation.model_name}' "
                "will store naive datetimes because USE_TZ=False. Consider "
                "enabling USE_TZ for timezone-aware storage."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for enabling USE_TZ.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """Enable timezone support in settings.py:

    USE_TZ = True

This stores datetimes as UTC in the database (TIMESTAMP WITH TIME ZONE
on PostgreSQL) and converts to the local timezone for display.

Benefits:
- Correct handling of daylight saving time transitions
- Easy support for multiple timezones
- Consistent datetime storage across the application
"""


class AddFieldWithDefaultRule(BaseRule):
    """Detect adding NOT NULL field with a Python-level default.

    When adding a NOT NULL field with a default value, Django:
    1. Adds the column with the default
    2. For each existing row, writes the default value

    On large tables, this can be very slow because Django applies the
    default in Python rather than using a database-level DEFAULT clause.

    Safe pattern:
    - Add the field as nullable first
    - Backfill existing rows in batches
    - Then set NOT NULL
    """

    rule_id = "SM033"
    severity = Severity.WARNING
    description = "Adding NOT NULL field with default rewrites all existing rows"

    # Auto fields don't need this check
    AUTO_FIELD_TYPES = frozenset(
        {
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
        }
    )

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation adds a NOT NULL field with a default.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if a NOT NULL field has a Python-level default.
        """
        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        # Skip auto fields
        if field_type in self.AUTO_FIELD_TYPES:
            return None

        # Skip nullable fields (they don't rewrite rows)
        if getattr(field, "null", False):
            return None

        # Check if field has a default
        from django.db.models.fields import NOT_PROVIDED

        default_value = getattr(field, "default", NOT_PROVIDED)
        if default_value is NOT_PROVIDED:
            return None

        # Check for db_default (Django 5.0+) — if db_default is set,
        # the database handles it efficiently
        db_default = getattr(field, "db_default", NOT_PROVIDED)
        if db_default is not NOT_PROVIDED:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Adding NOT NULL field '{operation.name}' on "
                f"'{operation.model_name}' with a default value will rewrite "
                "all existing rows. On large tables, add as nullable first, "
                "backfill, then set NOT NULL."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for adding fields with defaults safely.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        field_name = getattr(operation, "name", "field_name")
        model_name = getattr(operation, "model_name", "model")

        return f"""Safe pattern for adding NOT NULL field with default:

1. Add field as nullable (instant, no row rewrite):
   migrations.AddField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.FieldType(null=True),
   )

2. Backfill existing rows in batches:
   def backfill(apps, schema_editor):
       Model = apps.get_model('app', '{model_name}')
       batch_size = 1000
       while Model.objects.filter({field_name}__isnull=True).exists():
           ids = list(Model.objects.filter({field_name}__isnull=True)
                      .values_list('id', flat=True)[:batch_size])
           Model.objects.filter(id__in=ids).update({field_name}=default_val)

3. Set NOT NULL in a separate migration:
   migrations.AlterField(
       model_name='{model_name}',
       name='{field_name}',
       field=models.FieldType(null=False, default=default_val),
   )

Alternative (Django 5.0+): Use db_default for database-level defaults:
   field=models.IntegerField(db_default=0)
"""


class PreferIdentityRule(BaseRule):
    """Detect AutoField/BigAutoField on PostgreSQL with Django < 4.0.

    Before Django 4.0, AutoField/BigAutoField used SERIAL/BIGSERIAL
    columns in PostgreSQL. Starting with Django 4.0, they use IDENTITY
    columns which are the PostgreSQL-recommended approach.

    If you're on Django < 4.0, consider using IDENTITY columns via RunSQL.
    """

    rule_id = "SM034"
    severity = Severity.INFO
    description = "Consider IDENTITY columns instead of SERIAL on PostgreSQL"
    db_vendors = ["postgresql"]

    AUTO_FIELD_TYPES = frozenset(
        {
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
        }
    )

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if auto fields use SERIAL on older Django.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if Django < 4.0 and using auto fields.
        """
        import django

        if django.VERSION >= (4, 0):
            return None

        if not isinstance(operation, migrations.AddField):
            return None

        field = operation.field
        field_type = field.__class__.__name__

        if field_type not in self.AUTO_FIELD_TYPES:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                f"Field '{operation.name}' on '{operation.model_name}' uses "
                f"{field_type} which creates a SERIAL column on PostgreSQL. "
                "IDENTITY columns are recommended. Upgrade to Django 4.0+ "
                "for automatic IDENTITY column support."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for using IDENTITY columns.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """PostgreSQL IDENTITY columns vs SERIAL:

SERIAL columns have ownership issues and are considered legacy.
IDENTITY columns (PostgreSQL 10+) are the recommended approach.

Option 1: Upgrade to Django 4.0+ (recommended)
   Django 4.0+ automatically uses IDENTITY columns.

Option 2: Use RunSQL to create IDENTITY columns manually:
   migrations.RunSQL(
       sql='ALTER TABLE myapp_model ALTER COLUMN id '
           'ADD GENERATED BY DEFAULT AS IDENTITY',
       reverse_sql='ALTER TABLE myapp_model ALTER COLUMN id '
                   'DROP IDENTITY',
   )
"""
