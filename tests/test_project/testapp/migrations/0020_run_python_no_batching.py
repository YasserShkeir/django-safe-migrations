"""Migration with RunPython without batching.

This migration should be flagged by SM026 (WARNING level).
Using .all() without .iterator() in data migrations can cause memory issues.
"""

from django.db import migrations


def update_all_users(apps, schema_editor):
    """Update every user one by one (intentionally memory-heavy fixture)."""
    User = apps.get_model("testapp", "User")
    # Loads the entire table at once on purpose for the SM026 test
    for user in User.objects.all():
        user.order = 0
        user.save()


def noop(apps, schema_editor):
    """No-op reverse operation."""
    pass


class Migration(migrations.Migration):
    """RunPython with unbatched query."""

    dependencies = [
        ("testapp", "0019_fk_without_index"),
    ]

    operations = [
        # This should trigger SM026 - .all() without .iterator()
        migrations.RunPython(update_all_users, noop),
    ]
