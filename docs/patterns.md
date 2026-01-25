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

## Changing null=True to null=False

### The Problem

Changing a field from nullable to NOT NULL requires PostgreSQL to scan all rows
to verify no NULL values exist. If NULL values exist, the migration fails.

### Unsafe Pattern

```python
# ❌ Will fail if any NULL values exist
migrations.AlterField(
    model_name='user',
    name='nickname',
    field=models.CharField(max_length=100, null=False),  # Was null=True
)
```

### Safe Pattern

```python
# Migration 1: Backfill NULL values
def backfill_nicknames(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.filter(nickname__isnull=True).update(nickname='')

migrations.RunPython(backfill_nicknames, migrations.RunPython.noop)
```

```python
# Migration 2: Now safe to add NOT NULL
migrations.AlterField(
    model_name='user',
    name='nickname',
    field=models.CharField(max_length=100, null=False, default=''),
)
```

For large tables on PostgreSQL, use the NOT VALID pattern:

```python
# Add constraint as NOT VALID
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_user
        ADD CONSTRAINT nickname_not_null
        CHECK (nickname IS NOT NULL)
        NOT VALID;
    ''',
    reverse_sql='ALTER TABLE myapp_user DROP CONSTRAINT nickname_not_null;',
)
```

```python
# Validate constraint (can run while table is in use)
migrations.RunSQL(
    sql='ALTER TABLE myapp_user VALIDATE CONSTRAINT nickname_not_null;',
    reverse_sql=migrations.RunSQL.noop,
)
```

```python
# Now add the actual NOT NULL (instant since constraint already validated)
migrations.RunSQL(
    sql='ALTER TABLE myapp_user ALTER COLUMN nickname SET NOT NULL;',
    reverse_sql='ALTER TABLE myapp_user ALTER COLUMN nickname DROP NOT NULL;',
)
```

______________________________________________________________________

## Adding unique=True via AlterField

### The Problem

Adding `unique=True` via AlterField creates a unique index while holding a lock,
blocking writes for the duration of index creation.

### Unsafe Pattern

```python
# ❌ Locks table during index creation
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.EmailField(unique=True),
)
```

### Safe Pattern (PostgreSQL)

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    operations = [
        # Step 1: Create unique index concurrently
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(
                fields=['email'],
                name='user_email_uniq_idx',
            ),
        ),
    ]
```

```python
# Step 2: Add unique constraint using the index
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_user
        ADD CONSTRAINT user_email_unique
        UNIQUE USING INDEX user_email_uniq_idx;
    ''',
    reverse_sql='ALTER TABLE myapp_user DROP CONSTRAINT user_email_unique;',
)
```

______________________________________________________________________

## Adding ManyToMany Fields

### The Problem

Adding a ManyToManyField creates a new junction table. While generally safe,
it's good to be aware of what's happening.

### Pattern

```python
# This creates a new table: myapp_article_tags
migrations.AddField(
    model_name='article',
    name='tags',
    field=models.ManyToManyField('tags.Tag', blank=True),
)
```

### Considerations

- Junction table is empty initially (safe)
- No locks on existing tables
- May want to add indexes on the junction table for performance

```python
# Optional: Add index for reverse lookups
migrations.RunSQL(
    sql='''
        CREATE INDEX CONCURRENTLY myapp_article_tags_tag_idx
        ON myapp_article_tags(tag_id);
    ''',
    reverse_sql='DROP INDEX myapp_article_tags_tag_idx;',
)
```

______________________________________________________________________

## ForeignKey Without Index

### The Problem

By default, Django creates an index on ForeignKey fields. If you disable this
with `db_index=False`, JOIN queries can become very slow on large tables.

### Pattern to Avoid

```python
# ❌ No index means slow JOINs
migrations.AddField(
    model_name='order',
    name='customer',
    field=models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        db_index=False,  # Don't do this unless you have a good reason
    ),
)
```

### When db_index=False is OK

- The table will always be small
- You're creating a covering index that includes this field
- The field is never used in WHERE or JOIN clauses

```python
# ✅ OK if you have a covering index
migrations.AddField(
    model_name='order',
    name='customer',
    field=models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        db_index=False,
    ),
)

# Add a covering index instead
migrations.AddIndex(
    model_name='order',
    index=models.Index(
        fields=['customer', 'created_at'],
        name='order_customer_created_idx',
    ),
)
```

______________________________________________________________________

## Expensive Default Callables

### The Problem

Using callables like `timezone.now` as defaults means Django calls the function
once per row during backfill, which can be slow for large tables.

### Pattern to Consider

```python
# This is fine for new tables
migrations.AddField(
    model_name='user',
    name='created_at',
    field=models.DateTimeField(default=timezone.now),
)
```

### For Large Existing Tables

```python
# Migration 1: Add with static default
migrations.AddField(
    model_name='user',
    name='last_login',
    field=models.DateTimeField(null=True),  # Nullable initially
)
```

```python
# Migration 2: Backfill in batches with explicit value
def backfill_last_login(apps, schema_editor):
    from django.utils import timezone
    User = apps.get_model('myapp', 'User')
    now = timezone.now()  # Single value for all rows
    batch_size = 10000

    while User.objects.filter(last_login__isnull=True).exists():
        ids = list(
            User.objects.filter(last_login__isnull=True)
            .values_list('id', flat=True)[:batch_size]
        )
        User.objects.filter(id__in=ids).update(last_login=now)

migrations.RunPython(backfill_last_login, migrations.RunPython.noop)
```

______________________________________________________________________

## Data Migrations with Large Tables

### The Problem

Using `.all()` without `.iterator()` loads the entire table into memory.

### Unsafe Pattern

```python
# ❌ Loads all rows into memory at once
def migrate_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    for user in User.objects.all():  # OOM on large tables!
        user.name = user.name.title()
        user.save()
```

### Safe Pattern

```python
# ✅ Process in batches
def migrate_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    batch_size = 1000

    while True:
        batch = list(
            User.objects.filter(name_migrated=False)[:batch_size]
        )
        if not batch:
            break

        for user in batch:
            user.name = user.name.title()
            user.name_migrated = True

        User.objects.bulk_update(batch, ['name', 'name_migrated'])
```

Or use `.iterator()`:

```python
# ✅ Uses server-side cursor
def migrate_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    for user in User.objects.all().iterator(chunk_size=1000):
        # Process one at a time, memory efficient
        user.name = user.name.title()
        user.save(update_fields=['name'])
```

______________________________________________________________________

## Summary Table

| Operation              | Risk                 | Safe Pattern                           |
| ---------------------- | -------------------- | -------------------------------------- |
| Add NOT NULL column    | Table lock           | Add nullable → backfill → add NOT NULL |
| Create index           | Write lock           | `AddIndexConcurrently` (PostgreSQL)    |
| Add unique constraint  | Table scan + lock    | Create unique index first              |
| Add foreign key        | Validates all rows   | `NOT VALID` then `VALIDATE`            |
| Remove column          | Code breaks          | Remove code first, then column         |
| Rename column          | Code breaks          | Add new → migrate data → remove old    |
| Change column type     | Table rewrite        | Add new column → migrate → remove old  |
| Add CHECK constraint   | Validates all rows   | `NOT VALID` then `VALIDATE`            |
| Add enum value         | Transaction fails    | `atomic = False`                       |
| null=True → null=False | Scan + possible fail | Backfill NULLs first                   |
| Add unique via Alter   | Table lock           | Create index concurrently first        |
| Add ManyToMany         | Creates new table    | Generally safe, consider indexes       |
| FK without index       | Slow JOINs           | Keep default index or add covering     |
| Expensive default      | Slow backfill        | Use static default, backfill manually  |
| Large data migration   | Memory issues        | Use `.iterator()` or batch processing  |
