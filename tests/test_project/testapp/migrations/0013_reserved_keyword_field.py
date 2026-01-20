"""Migration with reserved keyword column names.

This migration should be flagged by SM019 (INFO level).
Using SQL reserved keywords as column names can cause issues.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add fields with reserved keyword names."""

    dependencies = [
        ("testapp", "0012_concurrent_index_in_atomic"),
    ]

    operations = [
        # 'order' is a SQL reserved keyword
        migrations.AddField(
            model_name="user",
            name="order",
            field=models.IntegerField(default=0),
        ),
        # 'type' is also a reserved keyword
        migrations.AddField(
            model_name="user",
            name="type",
            field=models.CharField(max_length=50, default="default"),
        ),
    ]
