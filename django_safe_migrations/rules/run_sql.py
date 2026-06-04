"""Rules for RunSQL and RunPython operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


def _split_sql_statements(sql: object) -> list[str]:
    """Return the individual SQL statements of a ``RunSQL.sql`` value, in order.

    ``RunSQL.sql`` may be a single string, a list/tuple of strings, or a list
    of ``(sql, params)`` tuples. Multi-statement strings are split on ``;``.
    Element/statement order is preserved so callers can reason about ordering.
    """
    raw_chunks: list[str] = []
    if isinstance(sql, (list, tuple)):
        for element in sql:
            if isinstance(element, (list, tuple)) and element:
                raw_chunks.append(str(element[0]))
            else:
                raw_chunks.append(str(element))
    else:
        raw_chunks.append(str(sql))

    statements: list[str] = []
    for chunk in raw_chunks:
        for stmt in chunk.split(";"):
            stmt = stmt.strip()
            if stmt:
                statements.append(stmt)
    return statements


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

    # Patterns that indicate adding enum value. The type name may be
    # schema-qualified (myschema.my_enum) or double-quoted ("My Enum").
    ENUM_ADD_PATTERNS = [
        r'ALTER\s+TYPE\s+(?:"[^"]+"|[\w.]+)\s+ADD\s+VALUE',
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


class SQLInjectionPatternRule(BaseRule):
    """Detect potential SQL injection patterns in RunSQL.

    RunSQL operations that use string formatting or interpolation
    may be vulnerable to SQL injection if the values come from
    untrusted sources.

    This rule detects common patterns that suggest string interpolation:
    - %s or %(name)s (Python % formatting)
    - {name} or {} (Python format/f-string)
    - String concatenation patterns

    Note: This rule may have false positives for legitimate
    parameterized queries. Use inline suppression if needed.
    """

    rule_id = "SM024"
    severity = Severity.ERROR
    description = "Potential SQL injection pattern detected in RunSQL"

    # Patterns that suggest string interpolation (potential SQL injection)
    # Each pattern is checked against the SQL text of RunSQL operations
    DANGEROUS_PATTERNS = [
        # %s not inside quotes (avoid matching LIKE '%something%')
        (r"(?<!')%s(?!')", "Python string formatting (%s)"),
        (r"%\([^)]+\)s", "Python named formatting (%(name)s)"),
        # {name} with identifier inside (avoid matching empty {} for arrays/JSON)
        (r"\{[a-zA-Z_]\w*\}", "Python format string ({name})"),
        (r"\$\{[^}]+\}", "Shell-style substitution (${var})"),
        (r"'\s*\+\s*[a-zA-Z_]", "String concatenation ('+ var)"),
        (r"[a-zA-Z_]\s*\+\s*'", "String concatenation (var +')"),
        (r'"\s*\+\s*[a-zA-Z_]', 'String concatenation ("+ var)'),
        (r'[a-zA-Z_]\s*\+\s*"', 'String concatenation (var +")'),
    ]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if RunSQL contains potential SQL injection patterns.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if dangerous patterns are found, None otherwise.
        """
        if not isinstance(operation, migrations.RunSQL):
            return None

        # Get the SQL string(s)
        sql = getattr(operation, "sql", "")

        # Handle case where sql is a list of statements
        if isinstance(sql, (list, tuple)):
            sql_str = " ".join(str(s) for s in sql)
        else:
            sql_str = str(sql)

        # Check for dangerous patterns
        for pattern, description in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_str):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"RunSQL contains potential SQL injection pattern: "
                        f"{description}. If this is intentional "
                        "parameterization, suppress this warning."
                    ),
                )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for safe SQL in migrations.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """Avoid SQL injection in migrations:

1. Use static SQL strings (safest):
   migrations.RunSQL(
       sql='CREATE INDEX idx ON users (email)',
       reverse_sql='DROP INDEX idx',
   )

2. For parameterized queries, use RunPython instead:
   def create_index(apps, schema_editor):
       with schema_editor.connection.cursor() as cursor:
           cursor.execute(
               'CREATE INDEX %s ON %s (%s)',
               [index_name, table_name, column_name]
           )

   migrations.RunPython(create_index, ...)

3. If you must use dynamic SQL, validate inputs strictly:
   - Whitelist allowed values
   - Use identifier quoting for table/column names
   - Never interpolate user input directly

   Note: migrations.RunSQL does NOT accept a `params` argument. To run a
   parameterized query, use RunPython with a cursor instead:

   def run(apps, schema_editor):
       with schema_editor.connection.cursor() as cursor:
           cursor.execute('UPDATE t SET c = %s WHERE id = %s', [value, pk])

4. If this warning is a false positive, suppress it inline:

   migrations.RunSQL(  # safe-migrations: ignore SM024
       sql="UPDATE t SET ratio = paid / total * 100",
   )
"""


class RunPythonNoBatchingRule(BaseRule):
    """Detect RunPython that may load all rows into memory.

    RunPython operations that use .all() without .iterator() or
    batching can load the entire table into memory, causing:
    - Out of memory errors on large tables
    - Long-running transactions that block other operations

    Safe pattern:
    - Use .iterator(chunk_size=N)
    - Process in batches with slicing
    - Use .values() or .values_list() when possible
    """

    rule_id = "SM026"
    severity = Severity.WARNING
    description = "RunPython may load all rows into memory without batching"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if RunPython loads all rows without batching.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if the operation may load all rows, None otherwise.
        """
        if not isinstance(operation, migrations.RunPython):
            return None

        # Get the forward function
        code_func = getattr(operation, "code", None)
        if code_func is None:
            return None

        # Try to get the source code
        try:
            import inspect

            source = inspect.getsource(code_func)
        except (OSError, TypeError):
            # Can't get source (e.g., lambda, built-in, or file not available)
            return None

        # Check for .all() without iterator or batching
        has_all = ".all()" in source
        has_iterator = ".iterator(" in source
        has_batching = any(
            pattern in source.lower()
            for pattern in ["chunk", "batch", "[:batch", "[: batch", "[:1000", "[0:"]
        )
        has_values = ".values(" in source or ".values_list(" in source

        # If using .all() without any batching mechanism
        if has_all and not has_iterator and not has_batching and not has_values:
            func_name = getattr(code_func, "__name__", "function")
            return self.create_issue(
                operation=operation,
                migration=migration,
                message=(
                    f"RunPython function '{func_name}' uses .all() without "
                    ".iterator() or batching. This may load all rows into memory."
                ),
            )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for batching in RunPython.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with the suggested safe pattern.
        """
        return """Avoid loading all rows into memory in RunPython:

1. Use iterator() with chunk_size:
   def migrate_data(apps, schema_editor):
       Model = apps.get_model('app', 'Model')
       for obj in Model.objects.all().iterator(chunk_size=1000):
           obj.new_field = transform(obj.old_field)
           obj.save()

2. Process in explicit batches:
   def migrate_data(apps, schema_editor):
       Model = apps.get_model('app', 'Model')
       batch_size = 1000
       total = Model.objects.count()

       for start in range(0, total, batch_size):
           batch = Model.objects.all()[start:start + batch_size]
           for obj in batch:
               ...

3. Use bulk_update for efficiency:
   def migrate_data(apps, schema_editor):
       Model = apps.get_model('app', 'Model')
       batch_size = 1000

       objs = list(Model.objects.filter(
           needs_update=True
       )[:batch_size])

       while objs:
           for obj in objs:
               obj.field = new_value
           Model.objects.bulk_update(objs, ['field'])

           objs = list(Model.objects.filter(
               needs_update=True
           )[:batch_size])

4. Use values/values_list when you don't need model instances:
   ids = list(Model.objects.values_list('id', flat=True))
"""


class RequireLockTimeoutRule(BaseRule):
    r"""Detect RunSQL with DDL but no SET lock_timeout.

    When running DDL statements (ALTER TABLE, CREATE INDEX, etc.) via
    RunSQL, it's good practice to set a lock_timeout to prevent the
    migration from waiting indefinitely for a lock.

    Without lock_timeout, a DDL statement can block while waiting for
    an exclusive lock, and in turn block all subsequent queries.

    This is an informational rule to encourage defensive DDL.
    """

    rule_id = "SM035"
    severity = Severity.INFO
    description = "RunSQL with DDL should set lock_timeout to avoid blocking"

    # DDL patterns that benefit from lock_timeout
    DDL_PATTERNS = [
        r"ALTER\s+TABLE",
        r"CREATE\s+INDEX",
        r"DROP\s+INDEX",
        r"DROP\s+TABLE",
        r"CREATE\s+TABLE",
        r"TRUNCATE\s+",
    ]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        r"""Check if RunSQL has DDL without lock_timeout.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            \*\*kwargs: Additional context.

        Returns:
            An Issue if DDL lacks lock_timeout, None otherwise.
        """
        if not isinstance(operation, migrations.RunSQL):
            return None

        # A lock_timeout only protects a DDL statement if it is set BEFORE it.
        # Consider earlier operations in the migration: a prior RunSQL that sets
        # lock_timeout protects DDL in this operation; later ops do not.
        seen_lock_timeout = False
        for op in getattr(migration, "operations", []):
            if op is operation:
                break  # stop at the current op — later ops can't protect it
            if isinstance(op, migrations.RunSQL):
                op_text = " ".join(_split_sql_statements(getattr(op, "sql", "")))
                if "LOCK_TIMEOUT" in op_text.upper():
                    seen_lock_timeout = True
                    break

        # Then scan this operation's statements in order: a DDL statement that
        # has no preceding lock_timeout (here or in an earlier op) is unprotected.
        has_unprotected_ddl = False
        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            stmt_upper = statement.upper()
            if "LOCK_TIMEOUT" in stmt_upper:
                seen_lock_timeout = True
                continue
            if any(re.search(p, stmt_upper) for p in self.DDL_PATTERNS):
                if not seen_lock_timeout:
                    has_unprotected_ddl = True
                    break

        if not has_unprotected_ddl:
            return None

        return self.create_issue(
            operation=operation,
            migration=migration,
            message=(
                "RunSQL contains a DDL statement without a preceding SET "
                "lock_timeout. Set lock_timeout before the DDL (earlier in "
                "the SQL list or in an earlier operation) to prevent "
                "indefinite blocking while waiting for locks."
            ),
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for setting lock_timeout.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """Set lock_timeout before DDL to avoid indefinite blocking:

    migrations.RunSQL(
        sql=[
            "SET lock_timeout = '5s'",
            "ALTER TABLE myapp_model ADD COLUMN new_col INTEGER",
            "SET lock_timeout = '0'",  # Reset after
        ],
        reverse_sql="ALTER TABLE myapp_model DROP COLUMN new_col",
    )

Or set it at the migration level:

    migrations.RunSQL("SET lock_timeout = '5s'"),
    migrations.RunSQL(
        sql="ALTER TABLE myapp_model ...",
        reverse_sql="ALTER TABLE myapp_model ...",
    ),
    migrations.RunSQL("SET lock_timeout = '0'"),

If the lock can't be acquired within the timeout, the statement
will fail with an error instead of blocking other queries.
"""


class PreferIfExistsRule(BaseRule):
    """Detect CREATE/DROP TABLE without IF [NOT] EXISTS.

    Using CREATE TABLE without IF NOT EXISTS or DROP TABLE without
    IF EXISTS can cause migrations to fail if the table already exists
    (or doesn't exist). This makes migrations non-idempotent.

    Safe pattern:
    Always use IF NOT EXISTS / IF EXISTS for defensive DDL.
    """

    rule_id = "SM036"
    severity = Severity.INFO
    description = "Use IF [NOT] EXISTS for defensive CREATE/DROP TABLE"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if CREATE/DROP TABLE lacks IF [NOT] EXISTS.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context.

        Returns:
            An Issue if IF [NOT] EXISTS is missing, None otherwise.
        """
        if not isinstance(operation, migrations.RunSQL):
            return None

        # Evaluate each statement independently so a bare CREATE/DROP TABLE is
        # still flagged when a sibling statement uses IF [NOT] EXISTS. RunSQL.sql
        # may be a string, a list of strings, or a list of (sql, params) tuples;
        # multi-statement strings are split on ';'.
        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            stmt_upper = statement.upper()

            # CREATE TABLE without IF NOT EXISTS
            if re.search(r"CREATE\s+TABLE\b", stmt_upper) and not re.search(
                r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\b", stmt_upper
            ):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "CREATE TABLE without IF NOT EXISTS may fail if "
                        "the table already exists. Use IF NOT EXISTS for "
                        "idempotent migrations."
                    ),
                )

            # DROP TABLE without IF EXISTS
            if re.search(r"DROP\s+TABLE\b", stmt_upper) and not re.search(
                r"DROP\s+TABLE\s+IF\s+EXISTS\b", stmt_upper
            ):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "DROP TABLE without IF EXISTS may fail if the table "
                        "doesn't exist. Use IF EXISTS for idempotent migrations."
                    ),
                )

        return None

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for using IF [NOT] EXISTS.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix.
        """
        return """Use IF [NOT] EXISTS for defensive DDL:

    # Instead of:
    migrations.RunSQL("CREATE TABLE myapp_temp (id SERIAL PRIMARY KEY)")

    # Use:
    migrations.RunSQL(
        sql="CREATE TABLE IF NOT EXISTS myapp_temp (id SERIAL PRIMARY KEY)",
        reverse_sql="DROP TABLE IF EXISTS myapp_temp",
    )

    # Instead of:
    migrations.RunSQL("DROP TABLE myapp_temp")

    # Use:
    migrations.RunSQL(
        sql="DROP TABLE IF EXISTS myapp_temp",
        reverse_sql="CREATE TABLE IF NOT EXISTS myapp_temp (...)",
    )

This makes migrations idempotent and safe to re-run.
"""


class TruncateInRunSQLRule(BaseRule):
    """Detect TRUNCATE in RunSQL.

    ``TRUNCATE TABLE`` deletes all rows in a table, and ``TRUNCATE ... CASCADE``
    also deletes rows from every referencing table. Putting it in a migration
    is almost always a mistake and is unrecoverable.
    """

    rule_id = "SM048"
    severity = Severity.WARNING
    description = "TRUNCATE in a migration deletes all table data"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Flag a RunSQL statement that starts with TRUNCATE."""
        if not isinstance(operation, migrations.RunSQL):
            return None

        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            if re.match(r"TRUNCATE\b", statement, re.IGNORECASE):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "RunSQL contains TRUNCATE, which deletes all data in the "
                        "table. TRUNCATE ... CASCADE also deletes data from "
                        "referencing tables. Avoid TRUNCATE in migrations; delete "
                        "rows explicitly (and reversibly) if data removal is "
                        "intended."
                    ),
                )
        return None


class DropDatabaseInRunSQLRule(BaseRule):
    """Detect DROP DATABASE / DROP SCHEMA in RunSQL.

    Dropping a database or schema from a migration is catastrophic and
    irreversible; it should never appear in a migration.
    """

    rule_id = "SM050"
    severity = Severity.ERROR
    description = "DROP DATABASE/SCHEMA in a migration is catastrophic"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Flag a RunSQL statement that starts with DROP DATABASE/SCHEMA."""
        if not isinstance(operation, migrations.RunSQL):
            return None

        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            if re.match(r"DROP\s+(DATABASE|SCHEMA)\b", statement, re.IGNORECASE):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "RunSQL contains DROP DATABASE/SCHEMA, which destroys the "
                        "database or schema and all of its objects. This must not "
                        "run as part of a migration."
                    ),
                )
        return None


class TransactionNestingInRunSQLRule(BaseRule):
    """Detect explicit transaction control in RunSQL inside an atomic migration.

    Django wraps atomic migrations in a transaction. Issuing ``BEGIN``,
    ``COMMIT``, ``ROLLBACK``, or ``START TRANSACTION`` inside RunSQL then creates
    a nested transaction, which PostgreSQL does not truly support — the
    statements either error or leave the surrounding transaction in an
    unexpected state.
    """

    rule_id = "SM049"
    severity = Severity.ERROR
    description = "Explicit transaction control in RunSQL conflicts with atomic"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Flag transaction-control statements in an atomic migration."""
        if not isinstance(operation, migrations.RunSQL):
            return None

        # Only an issue inside the implicit transaction of an atomic migration.
        if not getattr(migration, "atomic", True):
            return None

        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            if re.match(
                r"(BEGIN|START\s+TRANSACTION|COMMIT|ROLLBACK)\b",
                statement,
                re.IGNORECASE,
            ):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "RunSQL contains explicit transaction control "
                        "(BEGIN/COMMIT/ROLLBACK) inside an atomic migration, which "
                        "Django already wraps in a transaction. This causes nested "
                        "transaction errors. Set atomic = False on the migration "
                        "or remove the explicit transaction statements."
                    ),
                )
        return None


class ConstraintMissingNotValidRule(BaseRule):
    """Detect ADD CONSTRAINT (CHECK / FOREIGN KEY) without NOT VALID.

    On PostgreSQL, adding a CHECK or FOREIGN KEY constraint validates every
    existing row under an ACCESS EXCLUSIVE lock. The safe pattern adds the
    constraint ``NOT VALID`` (a quick metadata change), then runs
    ``VALIDATE CONSTRAINT`` separately under a weaker lock.
    """

    rule_id = "SM047"
    severity = Severity.WARNING
    description = "ADD CONSTRAINT (CHECK/FK) without NOT VALID scans the table"
    db_vendors = ["postgresql"]

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Flag ALTER TABLE ... ADD CONSTRAINT ... CHECK/FK without NOT VALID."""
        if not isinstance(operation, migrations.RunSQL):
            return None

        for statement in _split_sql_statements(getattr(operation, "sql", "")):
            upper = statement.upper()
            if (
                re.search(r"\bALTER\s+TABLE\b", upper)
                and re.search(r"\bADD\s+CONSTRAINT\b", upper)
                and re.search(r"\b(FOREIGN\s+KEY|CHECK)\b", upper)
                and "NOT VALID" not in upper
            ):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        "RunSQL adds a CHECK/FOREIGN KEY constraint without "
                        "NOT VALID, which scans the whole table under an ACCESS "
                        "EXCLUSIVE lock. Add the constraint NOT VALID, then run "
                        "VALIDATE CONSTRAINT in a separate statement/migration."
                    ),
                )
        return None


def _get_runpython_source(func: object) -> Optional[str]:
    """Return the dedented source of a RunPython function, or None.

    Mirrors the source-inspection approach used by SM026; returns None when the
    source is unavailable (lambda, C function, file not on disk).
    """
    try:
        import inspect
        import textwrap

        return textwrap.dedent(inspect.getsource(func))  # type: ignore[arg-type]
    except (OSError, TypeError):
        return None


class DirectModelImportInRunPythonRule(BaseRule):
    """Detect a RunPython function that imports a model directly.

    Using ``from app.models import MyModel`` (or ``import app.models``) inside a
    RunPython function uses the *current* model class, not the historical
    version at migration time. It works at first but breaks when the migration
    later runs against a fresh database. The safe approach is
    ``apps.get_model('app', 'MyModel')``.
    """

    rule_id = "SM037"
    severity = Severity.INFO
    description = "RunPython should use apps.get_model(), not a direct model import"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Flag a RunPython function with an inline model import."""
        if not isinstance(operation, migrations.RunPython):
            return None

        funcs = (
            getattr(operation, "code", None),
            getattr(operation, "reverse_code", None),
        )
        for func in funcs:
            if func is None:
                continue
            source = _get_runpython_source(func)
            if source is None:
                continue

            has_model_import = bool(
                re.search(
                    r"^\s*from\s+[\w.]+\.models\b\s+import\b", source, re.MULTILINE
                )
                or re.search(r"^\s*import\s+[\w.]+\.models\b", source, re.MULTILINE)
            )
            # Functions that use apps.get_model are doing it right; only flag a
            # direct import when get_model is not used, to keep noise low.
            if has_model_import and "apps.get_model" not in source:
                func_name = getattr(func, "__name__", "function")
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"RunPython function '{func_name}' imports a model "
                        "directly instead of using apps.get_model(). This uses "
                        "the current model, not the historical one, and breaks "
                        "on a fresh database. Use "
                        "apps.get_model('app_label', 'ModelName')."
                    ),
                )
        return None
