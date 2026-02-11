"""Squashed migration replacing 0002 and 0003.

This migration tests that the analyzer handles squashed migrations
without raising KeyError when replaced migrations are removed from
the graph but still exist on disk.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Squashed migration combining 0002 and 0003."""

    replaces = [
        ("testapp", "0002_unsafe_not_null"),
        ("testapp", "0003_safe_nullable"),
    ]

    dependencies = [
        ("testapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
