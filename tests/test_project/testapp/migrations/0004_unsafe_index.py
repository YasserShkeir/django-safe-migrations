"""Unsafe migration: adds index without CONCURRENTLY.

This migration should be flagged by SM010 on PostgreSQL.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add index without CONCURRENTLY."""

    dependencies = [
        ("testapp", "0003_safe_nullable"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
    ]
