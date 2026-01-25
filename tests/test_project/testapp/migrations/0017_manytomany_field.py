"""Migration adding a ManyToManyField.

This migration should be flagged by SM023 (INFO level).
ManyToMany fields create a junction table - generally safe but informational.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """AddField with ManyToManyField."""

    dependencies = [
        ("testapp", "0016_expensive_default"),
    ]

    operations = [
        # This should trigger SM023 - ManyToMany creates a junction table
        migrations.AddField(
            model_name="user",
            name="followers",
            field=models.ManyToManyField(
                to="testapp.User",
                related_name="following",
                blank=True,
            ),
        ),
    ]
