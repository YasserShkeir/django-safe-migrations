"""Unsafe migration: RunSQL without reverse_sql.

This migration should be flagged by SM007.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """RunSQL without reverse - cannot be rolled back."""

    dependencies = [
        ("testapp", "0005_drop_column"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX idx_user_created ON testapp_user (id)",
            # Missing reverse_sql!
        ),
    ]
