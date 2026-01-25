# Rules Reference

Django Safe Migrations includes rules to detect common unsafe migration patterns.

## Rule Severity Levels

| Level       | Meaning                                                    |
| ----------- | ---------------------------------------------------------- |
| **ERROR**   | Will likely break production or cause significant downtime |
| **WARNING** | May cause issues depending on your deployment strategy     |
| **INFO**    | Best practice recommendation                               |

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

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

______________________________________________________________________

## SM018: Concurrent Index in Atomic Migration

**Severity:** ERROR

**Databases:** PostgreSQL

### What it detects

Using `AddIndexConcurrently` or `RemoveIndexConcurrently` in a migration without
`atomic = False`:

```python
# ⚠️ ERROR
class Migration(migrations.Migration):
    # Missing atomic = False!
    operations = [
        AddIndexConcurrently(
            model_name='order',
            index=models.Index(fields=['status'], name='order_status_idx'),
        ),
    ]
```

### Why it's dangerous

PostgreSQL's `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. If you
forget to set `atomic = False`, the migration will fail at runtime with:

```
CREATE INDEX CONCURRENTLY cannot run inside a transaction block
```

### Safe pattern

```python
# ✅ SAFE: Set atomic = False
class Migration(migrations.Migration):
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name='order',
            index=models.Index(fields=['status'], name='order_status_idx'),
        ),
    ]
```

______________________________________________________________________

## SM019: Reserved Keyword Column Name

**Severity:** INFO

**Databases:** All

### What it detects

Using SQL reserved keywords as column names:

```python
# ⚠️ INFO
migrations.AddField(
    model_name='product',
    name='order',  # 'order' is a SQL keyword
    field=models.IntegerField(),
)
```

### Why it's problematic

While Django quotes identifiers, reserved keywords can cause issues with:

- Raw SQL queries
- Database tools and GUIs
- Third-party ORMs or reporting tools
- Future SQL standard compatibility

Common problematic names: `order`, `user`, `group`, `select`, `table`, `index`,
`key`, `primary`, `foreign`, `check`, `constraint`.

### Safe pattern

```python
# ✅ SAFE: Use descriptive, non-reserved names
migrations.AddField(
    model_name='product',
    name='sort_order',  # Descriptive and not reserved
    field=models.IntegerField(),
)
```

______________________________________________________________________

## SM020: AlterField to NOT NULL Without Backfill

**Severity:** ERROR

**Databases:** All

### What it detects

Changing a field from `null=True` to `null=False` without ensuring existing NULL
values are handled:

```python
# ⚠️ ERROR
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, null=False),  # Was null=True
)
```

### Why it's dangerous

If the table contains rows with NULL values in this column, the migration will
fail:

```
IntegrityError: column "email" contains null values
```

Even worse, in some databases this operation locks the table while checking all
rows.

### Safe pattern

```python
# ✅ SAFE: Backfill NULLs first, then alter

# Migration 1: Backfill NULL values
def backfill_emails(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    User.objects.filter(email__isnull=True).update(email='unknown@example.com')

migrations.RunPython(backfill_emails, migrations.RunPython.noop)

# Migration 2: Now safe to make NOT NULL
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, null=False),
)
```

______________________________________________________________________

## SM021: Adding UNIQUE via AlterField

**Severity:** ERROR

**Databases:** All

### What it detects

Adding a UNIQUE constraint via `AlterField`:

```python
# ⚠️ ERROR
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, unique=True),  # Adding unique=True
)
```

### Why it's dangerous

1. Requires scanning ALL rows to check for duplicates
2. Locks the table during the check
3. Fails if duplicates exist
4. On large tables, can cause significant downtime

### Safe pattern

```python
# ✅ SAFE: Use concurrent index (PostgreSQL)

# Migration 1: Create unique index concurrently
class Migration(migrations.Migration):
    atomic = False

    operations = [
        AddIndexConcurrently(
            model_name='user',
            index=models.Index(
                fields=['email'],
                name='user_email_unique_idx',
                condition=None,
            ),
        ),
    ]

# Migration 2: Add constraint using the index
migrations.AddConstraint(
    model_name='user',
    constraint=models.UniqueConstraint(
        fields=['email'],
        name='user_email_unique',
    ),
)
```

______________________________________________________________________

## SM022: Expensive Default Callable

**Severity:** WARNING

**Databases:** All

### What it detects

Using potentially expensive callables as field defaults:

```python
# ⚠️ WARNING
migrations.AddField(
    model_name='event',
    name='created_at',
    field=models.DateTimeField(default=datetime.now),  # Called for each row!
)
```

### Why it's problematic

When adding a column with a default, some databases:

1. Call the default function for EVERY existing row
2. For `datetime.now()`, this means N function calls
3. For `uuid.uuid4()`, this generates N UUIDs synchronously
4. Can significantly slow down migrations on large tables

### Safe pattern

```python
# ✅ SAFE: Use database-level defaults or backfill

# Option 1: Use auto_now_add (handled at ORM level)
field=models.DateTimeField(auto_now_add=True, null=True)

# Option 2: Use database default
migrations.RunSQL(
    sql="ALTER TABLE myapp_event ADD COLUMN created_at TIMESTAMP DEFAULT NOW()",
    reverse_sql="ALTER TABLE myapp_event DROP COLUMN created_at",
)

# Option 3: Add nullable, backfill, then make required
# Migration 1: Add as nullable
migrations.AddField(
    model_name='event',
    name='created_at',
    field=models.DateTimeField(null=True),
)
# Migration 2: Backfill with batch updates
# Migration 3: Make NOT NULL
```

______________________________________________________________________

## SM023: Adding ManyToMany Field

**Severity:** INFO

**Databases:** All

### What it detects

Adding a ManyToMany field:

```python
# ⚠️ INFO
migrations.AddField(
    model_name='article',
    name='tags',
    field=models.ManyToManyField(to='blog.Tag'),
)
```

### Why it's notable

Adding a ManyToMany field:

1. Creates a new junction table (e.g., `article_tags`)
2. The table creation itself is generally safe
3. However, be aware of subsequent operations that populate this table
4. Bulk inserts into the junction table can be slow

This is INFO severity because it's usually safe, but you should be aware of the
implications.

### Best practices

```python
# ✅ Consider: Add the field, but populate data carefully

# The migration (safe):
migrations.AddField(
    model_name='article',
    name='tags',
    field=models.ManyToManyField(to='blog.Tag'),
)

# When populating, use bulk operations:
def populate_tags(apps, schema_editor):
    Article = apps.get_model('blog', 'Article')
    Tag = apps.get_model('blog', 'Tag')
    through_model = Article.tags.through

    # Bulk create relationships
    relations = [
        through_model(article_id=a.id, tag_id=t.id)
        for a, t in compute_relationships()
    ]
    through_model.objects.bulk_create(relations, batch_size=1000)
```

______________________________________________________________________

## SM024: SQL Injection Pattern in RunSQL

**Severity:** ERROR

**Databases:** All

### What it detects

Potential SQL injection patterns in `RunSQL` operations:

```python
# ⚠️ ERROR
table_name = "users"  # Could come from untrusted source
migrations.RunSQL(
    sql=f"DROP TABLE {table_name}",  # String formatting = injection risk
)

# Also detected:
migrations.RunSQL(
    sql="SELECT * FROM users WHERE id = %s" % user_id,  # % formatting
)
```

### Why it's dangerous

While migrations typically run in trusted environments, SQL injection patterns
in migrations can:

1. Be accidentally triggered with wrong data
2. Set bad precedents for application code
3. Cause issues if migration code is reused
4. Be exploited if migration parameters come from external sources

### Safe pattern

```python
# ✅ SAFE: Use hardcoded SQL or Django's schema editor

# Option 1: Hardcoded SQL (when you control the values)
migrations.RunSQL(
    sql="CREATE INDEX idx_users_email ON users(email)",
    reverse_sql="DROP INDEX idx_users_email",
)

# Option 2: Use schema editor for dynamic operations
def create_index(apps, schema_editor):
    model = apps.get_model('myapp', 'User')
    schema_editor.add_index(model, models.Index(fields=['email']))

migrations.RunPython(create_index)
```

______________________________________________________________________

## SM025: Foreign Key Without Index

**Severity:** WARNING

**Databases:** All (primarily affects MySQL)

### What it detects

Adding a ForeignKey without `db_index=True` (or when `db_index=False`):

```python
# ⚠️ WARNING
migrations.AddField(
    model_name='order',
    name='customer',
    field=models.ForeignKey(
        to='myapp.Customer',
        on_delete=models.CASCADE,
        db_index=False,  # No index!
    ),
)
```

### Why it's problematic

Foreign keys without indexes cause:

1. Slow JOIN operations
2. Slow CASCADE deletes (must scan for related rows)
3. Slow reverse relation queries (`customer.order_set.all()`)
4. Lock contention on parent table deletes

Note: Django creates indexes for ForeignKey by default (`db_index=True`). This
rule catches when you explicitly disable it.

### Safe pattern

```python
# ✅ SAFE: Keep the default index (or explicitly enable)
migrations.AddField(
    model_name='order',
    name='customer',
    field=models.ForeignKey(
        to='myapp.Customer',
        on_delete=models.CASCADE,
        # db_index=True is the default
    ),
)
```

______________________________________________________________________

## SM026: RunPython Without Batching

**Severity:** WARNING

**Databases:** All

### What it detects

`RunPython` operations that use `.all()` without batching:

```python
# ⚠️ WARNING
def migrate_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')
    for user in User.objects.all():  # Loads ALL users into memory!
        user.name = user.name.title()
        user.save()

migrations.RunPython(migrate_data)
```

### Why it's dangerous

Loading all rows into memory:

1. Can exhaust server memory on large tables
2. Creates long-running transactions
3. Holds locks for extended periods
4. May timeout or be killed by the database

### Safe pattern

```python
# ✅ SAFE: Use batching with iterator() or chunked updates

def migrate_data(apps, schema_editor):
    User = apps.get_model('myapp', 'User')

    # Option 1: Use iterator with chunk_size
    for user in User.objects.iterator(chunk_size=1000):
        user.name = user.name.title()
        user.save()

    # Option 2: Bulk update in batches
    batch_size = 1000
    while True:
        batch = list(User.objects.filter(
            migrated=False
        )[:batch_size])
        if not batch:
            break
        for user in batch:
            user.name = user.name.title()
            user.migrated = True
        User.objects.bulk_update(batch, ['name', 'migrated'])

migrations.RunPython(migrate_data)
```

______________________________________________________________________

## SM027: Missing Merge Migration

**Severity:** ERROR

**Databases:** All

### What it detects

Multiple leaf migrations (migrations with no children) in the same app,
indicating a need for a merge migration:

```text
App 'myapp' has multiple leaf migrations:
  - 0005_add_field_a (from branch A)
  - 0005_add_field_b (from branch B)
```

### Why it's dangerous

Multiple leaf migrations cause:

1. Ambiguous migration state
2. Potential conflicts when both branches are applied
3. `makemigrations` confusion
4. CI/CD pipeline failures

This typically happens when two developers create migrations on separate
branches.

### Safe pattern

```bash
# ✅ SAFE: Create a merge migration
python manage.py makemigrations --merge myapp
```

This creates a merge migration that depends on both leaves:

```python
# 0006_merge_20240115_1234.py
class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0005_add_field_a'),
        ('myapp', '0005_add_field_b'),
    ]
    operations = []
```
