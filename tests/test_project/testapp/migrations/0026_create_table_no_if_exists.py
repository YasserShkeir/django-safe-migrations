"""Migration with CREATE TABLE without IF NOT EXISTS.

This migration should be flagged by SM036 (INFO level).
Using IF NOT EXISTS makes migrations idempotent.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """RunSQL with CREATE TABLE without IF NOT EXISTS."""

    dependencies = [
        ("testapp", "0025_run_sql_no_lock_timeout"),
    ]

    operations = [
        # SM036: CREATE TABLE without IF NOT EXISTS
        migrations.RunSQL(
            sql="CREATE TABLE testapp_temp_table (id SERIAL PRIMARY KEY, data TEXT)",
            reverse_sql="DROP TABLE IF EXISTS testapp_temp_table",
        ),
    ]
