"""Migration that drops NOT NULL (makes field nullable).

This migration should be flagged by SM029 (WARNING level).
Changing from NOT NULL to nullable can lead to data integrity issues.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Drop NOT NULL on username field."""

    dependencies = [
        ("testapp", "0021_autofield_primary_key"),
    ]

    operations = [
        # 'username' was NOT NULL (CharField default), now making it nullable
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
