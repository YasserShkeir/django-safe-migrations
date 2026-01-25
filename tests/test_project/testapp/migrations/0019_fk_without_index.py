"""Migration with ForeignKey without index.

This migration should be flagged by SM025 (WARNING level).
ForeignKey with db_index=False can cause slow joins and lookups.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """AddField with ForeignKey without index."""

    dependencies = [
        ("testapp", "0018_sql_injection_pattern"),
    ]

    operations = [
        # This should trigger SM025 - ForeignKey with db_index=False
        migrations.AddField(
            model_name="user",
            name="manager",
            field=models.ForeignKey(
                to="testapp.User",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                db_index=False,
                related_name="subordinates",
            ),
        ),
    ]
