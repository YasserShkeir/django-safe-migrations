"""Migration with suppression comment.

This migration has an unsafe operation but uses a suppression comment.
Used for testing inline suppression feature (v0.2.0).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add required field with suppression comment."""

    dependencies = [
        ("testapp", "0010_delete_model"),
    ]

    operations = [
        # safe-migrations: ignore SM001
        migrations.AddField(
            model_name="user",
            name="suppressed_field",
            field=models.CharField(
                max_length=100
            ),  # NOT NULL, no default - but suppressed
        ),
    ]
