"""Rules for naming conventions and reserved keywords."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation

logger = logging.getLogger("django_safe_migrations")

# SQL reserved keywords that are commonly problematic
# This is a subset of reserved words across PostgreSQL, MySQL, and SQLite
# Full lists are much longer, but these are the most commonly encountered
SQL_RESERVED_KEYWORDS = frozenset(
    {
        # SQL standard keywords
        "all",
        "and",
        "any",
        "as",
        "asc",
        "between",
        "by",
        "case",
        "check",
        "column",
        "constraint",
        "create",
        "cross",
        "current",
        "default",
        "delete",
        "desc",
        "distinct",
        "drop",
        "else",
        "end",
        "exists",
        "false",
        "for",
        "foreign",
        "from",
        "full",
        "group",
        "having",
        "in",
        "index",
        "inner",
        "insert",
        "into",
        "is",
        "join",
        "key",
        "left",
        "like",
        "limit",
        "not",
        "null",
        "on",
        "or",
        "order",
        "outer",
        "primary",
        "references",
        "right",
        "select",
        "set",
        "table",
        "then",
        "to",
        "true",
        "union",
        "unique",
        "update",
        "using",
        "values",
        "when",
        "where",
        "with",
        # Common problematic names
        "user",
        "users",
        "order",
        "orders",
        "group",
        "groups",
        "type",
        "status",
        "name",
        "date",
        "time",
        "timestamp",
        "key",
        "value",
        "comment",
        "admin",
        "level",
        "rank",
        "row",
        "rows",
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "offset",
        "result",
        "action",
        "mode",
        "role",
        "session",
    }
)

# PostgreSQL-specific reserved words
POSTGRESQL_RESERVED = frozenset(
    {
        "analyse",
        "analyze",
        "array",
        "asymmetric",
        "both",
        "cast",
        "collate",
        "current_catalog",
        "current_date",
        "current_role",
        "current_schema",
        "current_time",
        "current_timestamp",
        "current_user",
        "deferrable",
        "do",
        "except",
        "fetch",
        "freeze",
        "grant",
        "ilike",
        "initially",
        "intersect",
        "isnull",
        "lateral",
        "leading",
        "localtime",
        "localtimestamp",
        "natural",
        "notnull",
        "only",
        "overlaps",
        "placing",
        "returning",
        "similar",
        "some",
        "symmetric",
        "trailing",
        "user",
        "variadic",
        "verbose",
        "window",
    }
)

# MySQL-specific reserved words
MYSQL_RESERVED = frozenset(
    {
        "accessible",
        "add",
        "alter",
        "analyze",
        "asensitive",
        "before",
        "bigint",
        "binary",
        "blob",
        "both",
        "call",
        "cascade",
        "change",
        "char",
        "character",
        "collate",
        "condition",
        "continue",
        "convert",
        "database",
        "databases",
        "day_hour",
        "day_microsecond",
        "day_minute",
        "day_second",
        "dec",
        "decimal",
        "declare",
        "delayed",
        "describe",
        "deterministic",
        "distinctrow",
        "div",
        "double",
        "dual",
        "each",
        "elseif",
        "enclosed",
        "escaped",
        "exit",
        "explain",
        "float",
        "float4",
        "float8",
        "force",
        "fulltext",
        "generated",
        "get",
        "high_priority",
        "hour_microsecond",
        "hour_minute",
        "hour_second",
        "if",
        "ignore",
        "infile",
        "inout",
        "insensitive",
        "int",
        "int1",
        "int2",
        "int3",
        "int4",
        "int8",
        "integer",
        "interval",
        "io_after_gtids",
        "io_before_gtids",
        "iterate",
        "keys",
        "kill",
        "leading",
        "leave",
        "linear",
        "lines",
        "load",
        "localtime",
        "localtimestamp",
        "lock",
        "long",
        "longblob",
        "longtext",
        "loop",
        "low_priority",
        "master_bind",
        "master_ssl_verify_server_cert",
        "match",
        "maxvalue",
        "mediumblob",
        "mediumint",
        "mediumtext",
        "middleint",
        "minute_microsecond",
        "minute_second",
        "mod",
        "modifies",
        "natural",
        "no_write_to_binlog",
        "numeric",
        "optimize",
        "option",
        "optionally",
        "out",
        "outfile",
        "partition",
        "precision",
        "procedure",
        "purge",
        "range",
        "read",
        "reads",
        "real",
        "regexp",
        "release",
        "rename",
        "repeat",
        "replace",
        "require",
        "resignal",
        "restrict",
        "return",
        "revoke",
        "rlike",
        "schema",
        "schemas",
        "second_microsecond",
        "sensitive",
        "separator",
        "show",
        "signal",
        "smallint",
        "spatial",
        "specific",
        "sql",
        "sql_big_result",
        "sql_calc_found_rows",
        "sql_small_result",
        "sqlexception",
        "sqlstate",
        "sqlwarning",
        "ssl",
        "starting",
        "stored",
        "straight_join",
        "terminated",
        "tinyblob",
        "tinyint",
        "tinytext",
        "trigger",
        "undo",
        "unlock",
        "unsigned",
        "usage",
        "use",
        "utc_date",
        "utc_time",
        "utc_timestamp",
        "varbinary",
        "varchar",
        "varcharacter",
        "varying",
        "virtual",
        "while",
        "write",
        "xor",
        "year_month",
        "zerofill",
    }
)


class ReservedKeywordColumnRule(BaseRule):
    """Detect column names that are SQL reserved keywords.

    Using SQL reserved keywords as column names can cause issues:
    1. Raw SQL queries may fail without proper quoting
    2. Some ORMs and tools may not quote identifiers properly
    3. Database migrations and dumps may have compatibility issues
    4. Debugging and maintenance becomes harder

    Django quotes identifiers automatically in ORM queries, but raw SQL,
    database tools, and third-party libraries may not.

    Severity is INFO because this is a best practice warning,
    not a blocking issue.
    """

    rule_id = "SM019"
    severity = Severity.INFO
    description = "Column name is a SQL reserved keyword"

    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Check if operation uses a reserved keyword as column name.

        Args:
            operation: The migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (may include db_vendor).

        Returns:
            An Issue if a reserved keyword is used, None otherwise.
        """
        # Check AddField operations
        db_vendor: str | None = kwargs.get("db_vendor")  # type: ignore[assignment]
        if isinstance(operation, migrations.AddField):
            field_name = operation.name.lower()
            if self._is_reserved_keyword(field_name, db_vendor):
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"Column name '{operation.name}' on "
                        f"'{operation.model_name}' is a SQL reserved keyword"
                    ),
                )

        # Check CreateModel operations for all fields
        if isinstance(operation, migrations.CreateModel):
            reserved_fields = []
            for field_name, _field in operation.fields:
                if self._is_reserved_keyword(field_name.lower(), db_vendor):
                    reserved_fields.append(field_name)

            if reserved_fields:
                fields_str = ", ".join(f"'{f}'" for f in reserved_fields)
                return self.create_issue(
                    operation=operation,
                    migration=migration,
                    message=(
                        f"Model '{operation.name}' has fields with reserved "
                        f"keyword names: {fields_str}"
                    ),
                )

        return None

    def _is_reserved_keyword(self, name: str, db_vendor: str | None = None) -> bool:
        """Check if a name is a SQL reserved keyword.

        Args:
            name: The column/field name to check (lowercase).
            db_vendor: Optional database vendor for vendor-specific checks.

        Returns:
            True if the name is a reserved keyword.
        """
        # Check common SQL keywords
        if name in SQL_RESERVED_KEYWORDS:
            return True

        # Check vendor-specific keywords if vendor is specified
        if db_vendor == "postgresql" and name in POSTGRESQL_RESERVED:
            return True

        if db_vendor in ("mysql", "mariadb") and name in MYSQL_RESERVED:
            return True

        return False

    def get_suggestion(self, operation: Operation) -> str:
        """Return suggestion for handling reserved keyword names.

        Args:
            operation: The problematic operation.

        Returns:
            A multi-line string with suggestions.
        """
        if isinstance(operation, migrations.AddField):
            field_name = operation.name
        else:
            field_name = "field_name"

        return f"""Recommended alternatives for reserved keyword column names:

1. Use a more descriptive name:
   - Instead of 'user' → 'user_id', 'created_by', 'author'
   - Instead of 'order' → 'sort_order', 'sequence', 'display_order'
   - Instead of 'type' → 'item_type', 'category', 'kind'
   - Instead of 'status' → 'order_status', 'current_state'

2. Use db_column to keep the model field name different from DB column:
   class MyModel(models.Model):
       order_number = models.IntegerField(db_column='order')

3. If you must use a reserved word, Django will quote it in ORM queries,
   but be careful with:
   - Raw SQL queries (always quote identifiers)
   - Database tools and GUIs
   - Third-party libraries accessing the database
   - Exported SQL dumps

Current field name: '{field_name}'
"""
