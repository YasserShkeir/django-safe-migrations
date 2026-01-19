# Safe Migration Patterns

This guide shows safe patterns for common migration operations that can cause downtime or data loss if done incorrectly.

## Adding a NOT NULL Column

### The Problem

Adding a NOT NULL column without a default requires the database to:

1. Lock the entire table
2. Add the column to every row
3. Verify no NULL values exist

On large tables, this can lock the table for minutes or hours.

### Unsafe Pattern

```python
# ❌ This will lock the table and fail if rows exist
migrations.AddField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255),  # NOT NULL, no default!
)
```

### Safe Pattern

Split into three migrations:

```python
# Migration 1: Add nullable field
migrations.AddField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, null=True),
)
```

```python
# Migration 2: Backfill data
def backfill_emails(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    # Batch update to avoid memory issues
    batch_size = 1000
    while User.objects.filter(email__isnull=True).exists():
        ids = list(
            User.objects.filter(email__isnull=True)
            .values_list('id', flat=True)[:batch_size]
        )
        User.objects.filter(id__in=ids).update(email='unknown@example.com')

migrations.RunPython(backfill_emails, migrations.RunPython.noop)
```

```python
# Migration 3: Add NOT NULL constraint
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255),  # Now NOT NULL is safe
)
```

______________________________________________________________________

## Creating Indexes (PostgreSQL)

### The Problem

Standard index creation locks the table for writes during the entire operation.

### Unsafe Pattern

```python
# ❌ Locks table for writes
migrations.AddIndex(
    model_name='user',
    index=models.Index(fields=['email'], name='user_email_idx'),
)
```

### Safe Pattern

Use `AddIndexConcurrently` with `atomic = False`:

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    operations = [
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(fields=['email'], name='user_email_idx'),
        ),
    ]
```

!!! note
    `AddIndexConcurrently` is PostgreSQL-specific. For other databases, consider creating indexes during low-traffic periods.

______________________________________________________________________

## Adding Unique Constraints (PostgreSQL)

### The Problem

Adding a unique constraint requires a full table scan and locks the table.

### Unsafe Pattern

```python
# ❌ Locks table, scans all rows
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(fields=['email'], name='unique_email'),
)
```

### Safe Pattern

First create a unique index concurrently, then add the constraint using that index:

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False

    operations = [
        # Step 1: Create unique index concurrently
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(
                fields=['email'],
                name='user_email_unique_idx',
            ),
        ),
    ]
```

```python
# Step 2: Add constraint using the index (in a separate migration)
migrations.RunSQL(
    sql='ALTER TABLE myapp_user ADD CONSTRAINT unique_email UNIQUE USING INDEX user_email_unique_idx;',
    reverse_sql='ALTER TABLE myapp_user DROP CONSTRAINT unique_email;',
)
```

______________________________________________________________________

## Adding Foreign Keys

### The Problem

Adding a foreign key validates all existing rows, which can be slow on large tables.

### Unsafe Pattern

```python
# ❌ Validates all existing rows
migrations.AddField(
    model_name='order',
    name='user',
    field=models.ForeignKey('auth.User', on_delete=models.CASCADE),
)
```

### Safe Pattern (PostgreSQL)

Add the FK without validation, then validate separately:

```python
# Migration 1: Add FK without validation
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_order
        ADD CONSTRAINT order_user_fk
        FOREIGN KEY (user_id) REFERENCES auth_user(id)
        NOT VALID;
    ''',
    reverse_sql='ALTER TABLE myapp_order DROP CONSTRAINT order_user_fk;',
)
```

```python
# Migration 2: Validate FK (can run concurrently)
migrations.RunSQL(
    sql='ALTER TABLE myapp_order VALIDATE CONSTRAINT order_user_fk;',
    reverse_sql=migrations.RunSQL.noop,
)
```

______________________________________________________________________

## Removing Columns

### The Problem

During rolling deployments, old code may still reference the column.

### Unsafe Pattern

```python
# ❌ Old code will crash trying to SELECT this column
migrations.RemoveField(
    model_name='user',
    name='legacy_field',
)
```

### Safe Pattern

1. **First**: Remove all code references to the field
2. **Deploy**: Wait for all servers to have the new code
3. **Then**: Remove the field in a migration

```python
# Only after code is deployed everywhere
migrations.RemoveField(
    model_name='user',
    name='legacy_field',
)
```

!!! tip
    Consider using a two-phase approach:

    1. Migration 1: Make field nullable
    2. Wait for full deployment
    3. Migration 2: Remove the field

______________________________________________________________________

## Renaming Columns

### The Problem

Renaming breaks all existing code referencing the old name.

### Unsafe Pattern

```python
# ❌ Old code will crash
migrations.RenameField(
    model_name='user',
    old_name='name',
    new_name='full_name',
)
```

### Safe Pattern

1. Add the new column
2. Sync data between columns
3. Update code to use new column
4. Deploy everywhere
5. Remove old column

```python
# Migration 1: Add new column
migrations.AddField(
    model_name='user',
    name='full_name',
    field=models.CharField(max_length=255, null=True),
)

# Trigger or application code syncs data
```

```python
# Migration 2: After code deployed, remove old column
migrations.RemoveField(
    model_name='user',
    name='name',
)
```

______________________________________________________________________

## Changing Column Types

### The Problem

Changing a column type often requires a full table rewrite.

### Unsafe Changes

- `VARCHAR(100)` → `VARCHAR(50)` (truncation)
- `INTEGER` → `VARCHAR` (table rewrite)
- `VARCHAR` → `INTEGER` (validation + rewrite)

### Safe Changes

- `VARCHAR(100)` → `VARCHAR(200)` (increasing size is usually safe)
- `VARCHAR` → `TEXT` (safe on PostgreSQL)

### Safe Pattern for Type Changes

1. Add new column with new type
2. Backfill data in batches
3. Update code to use new column
4. Remove old column

______________________________________________________________________

## Adding CHECK Constraints

### The Problem

Adding a CHECK constraint validates all existing rows.

### Unsafe Pattern

```python
# ❌ Scans and locks table
migrations.AddConstraint(
    model_name='order',
    constraint=models.CheckConstraint(
        check=models.Q(amount__gte=0),
        name='positive_amount',
    ),
)
```

### Safe Pattern (PostgreSQL)

```python
# Add constraint as NOT VALID, then validate
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_order
        ADD CONSTRAINT positive_amount
        CHECK (amount >= 0)
        NOT VALID;
    ''',
    reverse_sql='ALTER TABLE myapp_order DROP CONSTRAINT positive_amount;',
)
```

```python
# Validate in separate migration
migrations.RunSQL(
    sql='ALTER TABLE myapp_order VALIDATE CONSTRAINT positive_amount;',
    reverse_sql=migrations.RunSQL.noop,
)
```

______________________________________________________________________

## RunSQL Best Practices

### Always Provide Reverse SQL

```python
# ✅ Reversible
migrations.RunSQL(
    sql='CREATE INDEX user_email_idx ON myapp_user(email);',
    reverse_sql='DROP INDEX user_email_idx;',
)
```

```python
# ❌ Not reversible - migration cannot be rolled back
migrations.RunSQL(
    sql='CREATE INDEX user_email_idx ON myapp_user(email);',
)
```

### Use State Operations

When using RunSQL, tell Django about the schema change:

```python
migrations.RunSQL(
    sql='ALTER TABLE myapp_user ADD COLUMN temp_field VARCHAR(100);',
    reverse_sql='ALTER TABLE myapp_user DROP COLUMN temp_field;',
    state_operations=[
        migrations.AddField(
            model_name='user',
            name='temp_field',
            field=models.CharField(max_length=100, null=True),
        ),
    ],
)
```

______________________________________________________________________

## RunPython Best Practices

### Always Provide Reverse Code

```python
def forward(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.filter(status='').update(status='active')

def reverse(apps, schema_editor):
    # Can't truly reverse, but provide a no-op or best effort
    pass

migrations.RunPython(forward, reverse)
```

### Batch Large Operations

```python
def backfill_in_batches(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    batch_size = 1000

    while True:
        # Get a batch of IDs
        ids = list(
            User.objects.filter(new_field__isnull=True)
            .values_list('id', flat=True)[:batch_size]
        )
        if not ids:
            break

        # Update batch
        User.objects.filter(id__in=ids).update(new_field='default')

migrations.RunPython(backfill_in_batches, migrations.RunPython.noop)
```

______________________________________________________________________

## PostgreSQL-Specific: Enum Values

### The Problem

Adding enum values inside a transaction fails on PostgreSQL.

### Unsafe Pattern

```python
# ❌ Fails: cannot add enum value inside transaction
migrations.RunSQL("ALTER TYPE myenum ADD VALUE 'new_value';")
```

### Safe Pattern

```python
class Migration(migrations.Migration):
    atomic = False  # Required!

    operations = [
        migrations.RunSQL(
            sql="ALTER TYPE myenum ADD VALUE 'new_value';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

!!! warning
    You cannot remove enum values in PostgreSQL. Plan your enums carefully.

______________________________________________________________________

## Summary Table

| Operation             | Risk               | Safe Pattern                           |
| --------------------- | ------------------ | -------------------------------------- |
| Add NOT NULL column   | Table lock         | Add nullable → backfill → add NOT NULL |
| Create index          | Write lock         | `AddIndexConcurrently` (PostgreSQL)    |
| Add unique constraint | Table scan + lock  | Create unique index first              |
| Add foreign key       | Validates all rows | `NOT VALID` then `VALIDATE`            |
| Remove column         | Code breaks        | Remove code first, then column         |
| Rename column         | Code breaks        | Add new → migrate data → remove old    |
| Change column type    | Table rewrite      | Add new column → migrate → remove old  |
| Add CHECK constraint  | Validates all rows | `NOT VALID` then `VALIDATE`            |
| Add enum value        | Transaction fails  | `atomic = False`                       |
