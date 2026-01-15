"""Unsafe migration: ALTER TYPE ADD VALUE inside transaction.

This migration should be flagged by SM012 on PostgreSQL.
Uses SeparateDatabaseAndState to prevent actual execution while still
having the RunSQL analyzed.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Add enum value in atomic migration - fails on PostgreSQL."""

    dependencies = [
        ("testapp", "0006_run_sql_no_reverse"),
    ]

    # atomic = True is the default, which is wrong for enum ADD VALUE
    operations = [
        # Use SeparateDatabaseAndState so the RunSQL is analyzed but not executed
        # The state_operations contain the RunSQL that triggers SM012
        # The database_operations is empty so nothing runs on the database
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[],
        ),
        # This RunSQL is what we actually want analyzed - it triggers SM012
        # but we need it to not execute, so we'll use a RunSQL.noop pattern
        migrations.RunSQL(
            sql=migrations.RunSQL.noop,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# For unit testing SM012, use mocked migrations with the actual SQL:
# migrations.RunSQL(sql="ALTER TYPE status_enum ADD VALUE 'pending'")
