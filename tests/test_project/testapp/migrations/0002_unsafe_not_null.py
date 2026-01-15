"""Unsafe migration: adds NOT NULL field without default.

This migration should be flagged by SM001.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add required email field without default."""

    dependencies = [
        ("testapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),  # NOT NULL, no default!
        ),
    ]
