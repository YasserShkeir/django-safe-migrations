"""Migration that adds a NOT NULL field with a default.

This migration should be flagged by SM033 (WARNING level).
Adding NOT NULL field with default rewrites all existing rows.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add NOT NULL field with Python-level default."""

    dependencies = [
        ("testapp", "0023_remove_index"),
    ]

    operations = [
        # SM033: NOT NULL field with default rewrites all rows
        migrations.AddField(
            model_name="user",
            name="status",
            field=models.CharField(max_length=20, default="active"),
        ),
    ]
