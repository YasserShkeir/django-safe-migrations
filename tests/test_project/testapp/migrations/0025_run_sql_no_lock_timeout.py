"""Migration with RunSQL DDL but no lock_timeout.

This migration should be flagged by SM035 (INFO level).
DDL statements should set lock_timeout to avoid indefinite blocking.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """RunSQL with DDL but no lock_timeout."""

    dependencies = [
        ("testapp", "0024_field_with_default"),
    ]

    operations = [
        # SM035: DDL without lock_timeout
        migrations.RunSQL(
            sql="ALTER TABLE testapp_user ADD COLUMN temp_col INTEGER",
            reverse_sql="ALTER TABLE testapp_user DROP COLUMN temp_col",
        ),
    ]
