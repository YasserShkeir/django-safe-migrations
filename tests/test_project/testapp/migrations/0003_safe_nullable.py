"""Safe migration - adds nullable field.

This migration should pass all checks.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add optional nickname field - SAFE."""

    dependencies = [
        ("testapp", "0002_unsafe_not_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
