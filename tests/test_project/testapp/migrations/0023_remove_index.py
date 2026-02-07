"""Migration that removes an index without CONCURRENTLY.

This migration should be flagged by SM030 (ERROR level, PostgreSQL only).
RemoveIndex without CONCURRENTLY takes ACCESS EXCLUSIVE lock.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove index without CONCURRENTLY."""

    dependencies = [
        ("testapp", "0022_drop_not_null"),
    ]

    operations = [
        # First add an index so we can remove it
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["username"], name="testapp_user_uname_idx"),
        ),
        # Then remove it without CONCURRENTLY - triggers SM030
        migrations.RemoveIndex(
            model_name="user",
            name="testapp_user_uname_idx",
        ),
    ]
