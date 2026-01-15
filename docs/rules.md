# Rules Reference

Django Safe Migrations includes rules to detect common unsafe migration patterns.

## Rule Severity Levels

| Level       | Meaning                                                    |
| ----------- | ---------------------------------------------------------- |
| **ERROR**   | Will likely break production or cause significant downtime |
| **WARNING** | May cause issues depending on your deployment strategy     |
| **INFO**    | Best practice recommendation                               |

---

## SM001: NOT NULL Without Default

**Severity:** ERROR

**Databases:** All

### What it detects

Adding a `NOT NULL` column without a default value:

```python
# ❌ UNSAFE
migrations.AddField(
    model_name='user',
    name='email',
    field=models.EmailField(),  # NOT NULL, no default
)
```

### Why it's dangerous

On PostgreSQL (and most databases), adding a NOT NULL column without a default:

1. Takes an `ACCESS EXCLUSIVE` lock on the table
2. Rewrites every row to add the new column
3. Blocks all reads and writes until complete

For large tables, this can take **minutes to hours**.

### Safe pattern

```python
# ✅ SAFE: Three-step process

# Migration 1: Add nullable column
migrations.AddField(
    model_name='user',
    name='email',
    field=models.EmailField(null=True),
)

# Migration 2: Backfill existing rows
def backfill(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    batch_size = 1000
    while User.objects.filter(email__isnull=True).exists():
        ids = list(User.objects.filter(email__isnull=True)
                   .values_list('id', flat=True)[:batch_size])
        User.objects.filter(id__in=ids).update(email='default@example.com')

migrations.RunPython(backfill, migrations.RunPython.noop)

# Migration 3: Add NOT NULL constraint
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.EmailField(),
)
```

---

## SM002: Unsafe Column Drop

**Severity:** WARNING

**Databases:** All

### What it detects

Dropping a column that may still be referenced by running code:

```python
# ⚠️ WARNING
migrations.RemoveField(
    model_name='user',
    name='legacy_field',
)
```

### Why it's dangerous

During a rolling deployment:

1. New code runs migration, drops column
2. Old code instances still running try to read column
3. **Application errors!**

### Safe pattern

Use the **expand/contract** pattern:

1. **Release 1:** Remove all code that reads/writes the column
2. **Release 2:** Deploy, verify no queries reference the column
3. **Release 3:** Drop the column

---

## SM003: Unsafe Table Drop

**Severity:** WARNING

**Databases:** All

### What it detects

Dropping a table (model) that may still be referenced:

```python
# ⚠️ WARNING
migrations.DeleteModel(name='LegacyModel')
```

### Why it's dangerous

Same as SM002, but for entire tables. Also:

- Foreign keys from other tables may cause constraint violations
- Raw SQL queries may still reference the table

### Safe pattern

1. Remove all code references to the model
2. Remove foreign keys in separate migrations
3. Deploy and verify no queries reference the table
4. Drop the table in a later release

---

## SM010: Non-Concurrent Index Creation

**Severity:** ERROR

**Databases:** PostgreSQL only

### What it detects

Creating an index without using `CONCURRENTLY`:

```python
# ❌ UNSAFE on PostgreSQL
migrations.AddIndex(
    model_name='user',
    index=models.Index(fields=['email'], name='user_email_idx'),
)
```

### Why it's dangerous

Standard index creation takes a `SHARE` lock that blocks:

- `INSERT`, `UPDATE`, `DELETE` operations
- Other `ALTER TABLE` operations

For large tables, this can take **minutes to hours** of write downtime.

### Safe pattern

```python
# ✅ SAFE: Use concurrent index
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
`atomic = False` is required because `CREATE INDEX CONCURRENTLY` cannot run inside a transaction.

---

## SM011: Non-Concurrent Unique Constraint

**Severity:** ERROR

**Databases:** PostgreSQL only

### What it detects

Adding a unique constraint without using a concurrent index:

```python
# ❌ UNSAFE on PostgreSQL
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(
        fields=['email'],
        name='unique_user_email',
    ),
)
```

### Why it's dangerous

PostgreSQL implements unique constraints using indexes. Adding one:

1. Creates a unique index (blocking writes)
2. Validates all existing rows (more blocking)

### Safe pattern

```python
# ✅ SAFE: Two-step process

# Migration 1: Create unique index concurrently
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(
                fields=['email'],
                name='unique_user_email_idx',
            ),
        ),
    ]

# Migration 2: Add constraint using existing index
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_user
        ADD CONSTRAINT unique_user_email
        UNIQUE USING INDEX unique_user_email_idx
    ''',
    reverse_sql='ALTER TABLE myapp_user DROP CONSTRAINT unique_user_email',
)
```

---

## SM004: Alter Column Type

**Severity:** WARNING

**Databases:** All (especially PostgreSQL)

### What it detects

Changing a column's type via AlterField:

```python
# ⚠️ WARNING
migrations.AlterField(
    model_name='product',
    name='price',
    field=models.DecimalField(max_digits=10, decimal_places=2),
)
```

### Why it's dangerous

Changing column types often requires:

1. Rewriting every row in the table
2. Taking an `ACCESS EXCLUSIVE` lock
3. Blocking all reads and writes

Even seemingly safe changes (like `Integer` → `BigInteger`) can trigger full table rewrites.

### Safe pattern

```python
# ✅ SAFE: Expand/Contract pattern

# Migration 1: Add new column
migrations.AddField(
    model_name='product',
    name='price_new',
    field=models.DecimalField(max_digits=10, decimal_places=2, null=True),
)

# Migration 2: Copy data in batches
def copy_data(apps, schema_editor):
    Product = apps.get_model('myapp', 'Product')
    batch_size = 1000
    for product in Product.objects.iterator(chunk_size=batch_size):
        product.price_new = product.price
        product.save(update_fields=['price_new'])

migrations.RunPython(copy_data, migrations.RunPython.noop)

# Migration 3: Switch application to use new column
# Migration 4: Drop old column
```

---

## SM005: Foreign Key Validates Existing Rows

**Severity:** WARNING

**Databases:** All

### What it detects

Adding a ForeignKey that validates existing rows:

```python
# ⚠️ WARNING
migrations.AddField(
    model_name='article',
    name='author',
    field=models.ForeignKey(
        to='auth.User',
        on_delete=models.CASCADE,
    ),
)
```

### Why it's dangerous

Adding a FK constraint:

1. Scans ALL existing rows to verify the constraint
2. Takes a `SHARE ROW EXCLUSIVE` lock on both tables
3. Blocks writes on large tables for extended periods

### Safe pattern

```python
# ✅ SAFE: Add FK without constraint validation

# Migration 1: Add FK without database constraint
migrations.AddField(
    model_name='article',
    name='author',
    field=models.ForeignKey(
        to='auth.User',
        on_delete=models.CASCADE,
        db_constraint=False,  # Skip constraint creation
    ),
)

# Migration 2: Add constraint with NOT VALID (PostgreSQL)
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_article
        ADD CONSTRAINT article_author_fk
        FOREIGN KEY (author_id) REFERENCES auth_user(id)
        NOT VALID
    ''',
    reverse_sql='ALTER TABLE myapp_article DROP CONSTRAINT article_author_fk',
)

# Migration 3: Validate constraint (doesn't block writes)
migrations.RunSQL(
    sql='ALTER TABLE myapp_article VALIDATE CONSTRAINT article_author_fk',
    reverse_sql=migrations.RunSQL.noop,
)
```

---

## SM006: Rename Column

**Severity:** INFO

**Databases:** All

### What it detects

Renaming a column:

```python
# ℹ️ INFO
migrations.RenameField(
    model_name='user',
    old_name='username',
    new_name='login',
)
```

### Why it's flagged

During a rolling deployment:

1. Migration renames column
2. Old application instances still expect old column name
3. Queries fail until all instances are updated

### Safe pattern

For zero-downtime deployments:

```python
# ✅ SAFE: Expand/Contract pattern

# Migration 1: Add new column
migrations.AddField(
    model_name='user',
    name='login',
    field=models.CharField(max_length=150, null=True),
)

# Migration 2: Copy data
def copy_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.update(login=F('username'))

migrations.RunPython(copy_data, migrations.RunPython.noop)

# Deploy: Update application to write to both columns, read from new
# Migration 3: Make NOT NULL, drop old column
```

---

## SM007: RunSQL Without Reverse

**Severity:** WARNING

**Databases:** All

### What it detects

RunSQL operations without reverse_sql:

```python
# ⚠️ WARNING
migrations.RunSQL(
    sql='CREATE INDEX idx_user_email ON users (email)',
)
```

### Why it's dangerous

Without `reverse_sql`:

1. Migration cannot be rolled back
2. May leave database in inconsistent state on failure
3. Breaks `migrate` command's ability to undo changes

### Safe pattern

```python
# ✅ SAFE: Always provide reverse_sql

migrations.RunSQL(
    sql='CREATE INDEX idx_user_email ON users (email)',
    reverse_sql='DROP INDEX idx_user_email',
)

# Or if the operation is intentionally irreversible:
migrations.RunSQL(
    sql='CREATE INDEX idx_user_email ON users (email)',
    reverse_sql=migrations.RunSQL.noop,  # Explicitly mark as no-op
)
```

---

## SM008: Large Data Migration

**Severity:** INFO

**Databases:** All

### What it detects

RunPython data migrations:

```python
# ℹ️ INFO
def update_all_users(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    for user in User.objects.all():
        user.name = user.name.upper()
        user.save()

migrations.RunPython(update_all_users, migrations.RunPython.noop)
```

### Why it's flagged

Data migrations can be slow because:

1. Loading all objects into memory
2. Individual `save()` calls (N+1 queries)
3. No batching or chunking
4. Long-running transactions

### Safe pattern

```python
# ✅ SAFE: Batch processing with iterator

def update_all_users(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    batch_size = 1000

    # Use iterator to avoid loading all objects
    for user in User.objects.iterator(chunk_size=batch_size):
        user.name = user.name.upper()
        user.save(update_fields=['name'])

# Or use bulk_update for better performance:
def update_all_users_bulk(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    batch_size = 1000

    users = User.objects.all()
    for batch in chunked(users.iterator(), batch_size):
        for user in batch:
            user.name = user.name.upper()
        User.objects.bulk_update(batch, ['name'])
```

---

## SM012: Enum Add Value in Transaction

**Severity:** ERROR

**Databases:** PostgreSQL only

### What it detects

Adding a value to an enum type inside a transaction:

```python
# ❌ UNSAFE on PostgreSQL
migrations.RunSQL(
    sql="ALTER TYPE status_enum ADD VALUE 'pending'",
)
```

### Why it's dangerous

PostgreSQL does not allow `ALTER TYPE ... ADD VALUE` inside a transaction block. Running this migration will cause:

```
ERROR: ALTER TYPE ... ADD VALUE cannot run inside a transaction block
```

### Safe pattern

```python
# ✅ SAFE: Set atomic = False

class Migration(migrations.Migration):
    atomic = False  # Required for ALTER TYPE ADD VALUE

    operations = [
        migrations.RunSQL(
            sql="ALTER TYPE status_enum ADD VALUE 'pending'",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

!!! note
Enum value additions cannot be easily reversed. Consider if you really need an enum, or if a regular VARCHAR would work better.

---

## SM013: Alter VARCHAR Length

**Severity:** WARNING

**Databases:** PostgreSQL

### What it detects

Decreasing the max_length of a CharField:

```python
# ⚠️ WARNING - if max_length is being decreased
migrations.AlterField(
    model_name='user',
    name='username',
    field=models.CharField(max_length=50),  # Was max_length=100
)
```

### Why it's dangerous

In PostgreSQL:

- **Increasing** max_length: Just a metadata change (safe)
- **Decreasing** max_length: Requires table rewrite + exclusive lock

The database must verify all existing data fits within the new length.

### Safe pattern

```python
# ✅ SAFE: Use a CHECK constraint instead

# Migration 1: Add CHECK constraint (doesn't rewrite table)
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_user
        ADD CONSTRAINT check_username_length
        CHECK (LENGTH(username) <= 50)
    ''',
    reverse_sql='ALTER TABLE myapp_user DROP CONSTRAINT check_username_length',
)

# Verify all data fits, then optionally alter the column type
# during a maintenance window if needed
```

---

## SM009: Adding Unique Constraint

**Severity:** ERROR

**Databases:** All (especially PostgreSQL)

### What it detects

Adding a unique constraint to an existing table:

```python
# ❌ UNSAFE
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(
        fields=['email', 'tenant_id'],
        name='unique_email_per_tenant',
    ),
)
```

### Why it's dangerous

Adding a unique constraint requires:

1. A full table scan to validate existing rows
2. Creating a unique index (blocking writes on PostgreSQL)

For large tables, this can take minutes to hours.

### Safe pattern

```python
# ✅ SAFE: Create index concurrently first

# Migration 1: Create unique index concurrently
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(
                fields=['email', 'tenant_id'],
                name='unique_email_tenant_idx',
            ),
        ),
    ]

# Migration 2: Add constraint using existing index
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(
        fields=['email', 'tenant_id'],
        name='unique_email_per_tenant',
    ),
)
```

---

## SM014: Rename Model

**Severity:** WARNING

**Databases:** All

### What it detects

Renaming a model (which renames the database table):

```python
# ⚠️ WARNING
migrations.RenameModel(
    old_name='OldUser',
    new_name='NewUser',
)
```

### Why it's dangerous

Renaming a model can cause:

1. Foreign keys from other apps may reference the old table name
2. Raw SQL queries using the table name will break
3. Database-level permissions may be lost
4. Indexes and constraints may need renaming

### Safe pattern

```python
# ✅ SAFE: Keep the old table name

class NewUser(models.Model):
    # ... fields ...

    class Meta:
        db_table = 'olduser'  # Keep the old table name
```

Or use the expand/contract pattern:

1. Create a new model with the new name
2. Copy data in a migration
3. Update all foreign keys and references
4. Remove the old model in a later release

---

## SM015: Alter Unique Together (Deprecated)

**Severity:** WARNING

**Databases:** All

### What it detects

Using the deprecated `AlterUniqueTogether` operation:

```python
# ⚠️ WARNING - deprecated
migrations.AlterUniqueTogether(
    name='user',
    unique_together={('email', 'tenant_id')},
)
```

### Why it's dangerous

`unique_together` is deprecated since Django 4.0. Using it:

1. Still requires a table scan to validate uniqueness
2. Doesn't support modern constraint features
3. May be removed in future Django versions

### Safe pattern

```python
# ✅ SAFE: Use UniqueConstraint instead
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(
        fields=['email', 'tenant_id'],
        name='unique_email_tenant',
    ),
)
```

`UniqueConstraint` provides more features:

- Conditional uniqueness (`condition` parameter)
- Partial indexes
- Better introspection support

---

## SM016: RunPython Without Reverse

**Severity:** INFO

**Databases:** All

### What it detects

`RunPython` operations without a `reverse_code` function:

```python
# ⚠️ INFO
migrations.RunPython(populate_defaults)  # No reverse_code
```

### Why it's dangerous

Without `reverse_code`, the migration cannot be rolled back. If something goes wrong:

1. You cannot easily revert the migration
2. Manual database fixes may be required
3. Deployment rollbacks become risky

### Safe pattern

```python
# ✅ SAFE: Always provide reverse_code

def populate_defaults(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    Model.objects.filter(field__isnull=True).update(field='default')

def reverse_defaults(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    Model.objects.filter(field='default').update(field=None)

migrations.RunPython(
    populate_defaults,
    reverse_code=reverse_defaults,
)

# Or if reversal isn't needed:
migrations.RunPython(
    populate_defaults,
    reverse_code=migrations.RunPython.noop,
)
```

---

## SM017: Adding Check Constraint

**Severity:** WARNING

**Databases:** PostgreSQL

### What it detects

Adding a check constraint to an existing table:

```python
# ⚠️ WARNING
migrations.AddConstraint(
    model_name='order',
    constraint=models.CheckConstraint(
        condition=models.Q(amount__gte=0),
        name='positive_amount',
    ),
)
```

### Why it's dangerous

Adding a check constraint requires PostgreSQL to validate ALL existing rows against the constraint. For large tables:

1. This can take a long time
2. It blocks writes during validation
3. May fail if existing data violates the constraint

### Safe pattern

```python
# ✅ SAFE: Add as NOT VALID first, then validate

# Migration 1: Add constraint as NOT VALID
migrations.RunSQL(
    sql='''
        ALTER TABLE myapp_order
        ADD CONSTRAINT positive_amount
        CHECK (amount >= 0)
        NOT VALID;
    ''',
    reverse_sql='ALTER TABLE myapp_order DROP CONSTRAINT positive_amount;',
)

# Migration 2: Validate in a separate step
migrations.RunSQL(
    sql='ALTER TABLE myapp_order VALIDATE CONSTRAINT positive_amount;',
    reverse_sql=migrations.RunSQL.noop,
)
```

The `NOT VALID` option adds the constraint without validating existing rows. The `VALIDATE CONSTRAINT` step:

- Only takes a `SHARE UPDATE EXCLUSIVE` lock (allows reads/writes)
- Validates rows incrementally
- Can be run during normal operation
