"""Unsafe migration: adding unique constraint.

This migration should be flagged by SM009.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add unique constraint - requires table scan."""

    dependencies = [
        ("testapp", "0007_enum_in_transaction"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_user_email",
            ),
        ),
    ]
