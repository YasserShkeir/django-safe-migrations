"""Migration with AlterField setting null=False.

This migration should be flagged by SM020 (ERROR level).
AlterField to null=False may fail if existing rows have NULL values.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """AlterField to set null=False on an existing field."""

    dependencies = [
        ("testapp", "0013_reserved_keyword_field"),
    ]

    operations = [
        # This should trigger SM020 - altering to null=False without backfill
        migrations.AlterField(
            model_name="user",
            name="order",
            field=models.IntegerField(null=False, default=0),
        ),
    ]
