"""Migration with AlterField adding unique=True.

This migration should be flagged by SM021 (ERROR level).
Adding unique constraint via AlterField scans and locks the entire table.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """AlterField to add unique constraint."""

    dependencies = [
        ("testapp", "0014_alterfield_null_false"),
    ]

    operations = [
        # This should trigger SM021 - adding unique via AlterField
        migrations.AlterField(
            model_name="user",
            name="type",
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
