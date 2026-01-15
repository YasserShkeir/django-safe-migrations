"""Unsafe migration: deletes a model (table).

This migration should be flagged by SM003.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Delete the entire Profile model - UNSAFE."""

    dependencies = [
        ("testapp", "0009_run_python_no_reverse"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Profile",
        ),
    ]
