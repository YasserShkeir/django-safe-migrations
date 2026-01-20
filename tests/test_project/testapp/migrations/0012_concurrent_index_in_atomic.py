"""Unsafe migration: concurrent index operation in atomic migration.

This migration should be flagged by SM018 on PostgreSQL.
AddIndexConcurrently cannot run inside a transaction block.
"""

from django.db import migrations, models

# Import conditionally to support older Django versions
try:
    from django.contrib.postgres.operations import AddIndexConcurrently
except ImportError:
    AddIndexConcurrently = None


class Migration(migrations.Migration):
    """Add concurrent index without atomic = False."""

    dependencies = [
        ("testapp", "0011_suppressed_not_null"),
    ]

    # Note: atomic = True is the default, which is wrong for concurrent ops
    # atomic = False  # This should be uncommented to fix the issue

    operations = (
        [
            AddIndexConcurrently(
                model_name="user",
                index=models.Index(fields=["name"], name="user_name_concurrent_idx"),
            ),
        ]
        if AddIndexConcurrently
        else []
    )
