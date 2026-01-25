"""Migration with expensive default callable.

This migration should be flagged by SM022 (WARNING level).
Using timezone.now or datetime.now as default is called per-row during backfill.
"""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    """AddField with expensive callable default."""

    dependencies = [
        ("testapp", "0015_alterfield_unique"),
    ]

    operations = [
        # This should trigger SM022 - timezone.now is called per row
        migrations.AddField(
            model_name="user",
            name="last_login",
            field=models.DateTimeField(default=timezone.now),
        ),
    ]
