"""Migration with AutoField primary key.

This migration should be flagged by SM028 (WARNING level).
AutoField uses 32-bit integers which can overflow at ~2.1 billion rows.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Create model with AutoField primary key."""

    dependencies = [
        ("testapp", "0020_run_python_no_batching"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegacyItem",
            fields=[
                (
                    "id",
                    models.AutoField(primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
    ]
