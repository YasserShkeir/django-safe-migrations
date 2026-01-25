"""Migration with SQL injection pattern in RunSQL.

This migration should be flagged by SM024 (ERROR level).
Using string formatting patterns in RunSQL can lead to SQL injection.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """RunSQL with dangerous string formatting patterns."""

    dependencies = [
        ("testapp", "0017_manytomany_field"),
    ]

    operations = [
        # This should trigger SM024 - %s formatting pattern
        migrations.RunSQL(
            sql="UPDATE testapp_user SET order = %s WHERE id = %s",
            reverse_sql="SELECT 1",  # Dummy reverse to avoid SM007
        ),
    ]
