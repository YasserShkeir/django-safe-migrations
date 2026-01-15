"""Unsafe migration: RunPython without reverse_code.

This migration should be flagged by SM016.
"""

from django.db import migrations


def populate_data(apps, schema_editor):
    """Populate some data."""
    pass  # Dummy function


class Migration(migrations.Migration):
    """RunPython without reverse - cannot be rolled back."""

    dependencies = [
        ("testapp", "0008_unique_constraint"),
    ]

    operations = [
        migrations.RunPython(
            populate_data,
            # Missing reverse_code!
        ),
    ]
