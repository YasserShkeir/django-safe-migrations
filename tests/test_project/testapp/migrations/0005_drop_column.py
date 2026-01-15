"""Unsafe migration: drops a column.

This migration should be flagged by SM002.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Drop the nickname column - UNSAFE during rolling deploy."""

    dependencies = [
        ("testapp", "0004_unsafe_index"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="nickname",
        ),
    ]
