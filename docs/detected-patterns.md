# Detected Patterns

This page shows exactly what patterns django-safe-migrations detects, using real migration examples from our test suite. Each example demonstrates an unsafe pattern, explains why it's dangerous, and shows the safe alternative.

## Quick Reference

| Pattern                                                                  | Rule  | Severity | Risk               |
| ------------------------------------------------------------------------ | ----- | -------- | ------------------ |
| [NOT NULL without default](#not-null-without-default)                    | SM001 | ERROR    | Table lock         |
| [Drop column](#drop-column)                                              | SM002 | WARNING  | Application errors |
| [Drop table](#drop-table)                                                | SM003 | WARNING  | Application errors |
| [Non-concurrent index](#non-concurrent-index-postgresql)                 | SM010 | ERROR    | Table lock         |
| [RunSQL without reverse](#runsql-without-reverse)                        | SM007 | WARNING  | Irreversible       |
| [Enum in transaction](#enum-value-in-transaction-postgresql)             | SM012 | ERROR    | Transaction fails  |
| [Unique constraint](#unique-constraint)                                  | SM009 | ERROR    | Table lock         |
| [RunPython without reverse](#runpython-without-reverse)                  | SM016 | INFO     | Irreversible       |
| [32-bit primary key](#32-bit-primary-key)                                | SM028 | WARNING  | Scalability        |
| [Non-concurrent index removal](#non-concurrent-index-removal-postgresql) | SM030 | ERROR    | Table lock         |
| [NOT NULL with Python default](#not-null-field-with-python-default)      | SM033 | WARNING  | Table rewrite      |
| [Missing lock_timeout](#missing-lock_timeout-in-runsql)                  | SM035 | INFO     | Blocking           |

______________________________________________________________________

## NOT NULL Without Default

**Rule:** SM001 | **Severity:** ERROR

### The Unsafe Pattern

```python
# testapp/migrations/0002_unsafe_not_null.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),  # NOT NULL, no default!
        ),
    ]
```

### Tool Output

```
ERROR [SM001] testapp/migrations/0002_unsafe_not_null.py:17
  Adding NOT NULL field 'email' to 'user' without a default value will lock the table
  Operation: AddField(user.email)

  Suggestion:
    Safe pattern for adding NOT NULL field:

    1. Migration 1 - Add field as nullable:
       migrations.AddField(
           model_name='user',
           name='email',
           field=models.CharField(max_length=255, null=True),
       )

    2. Data migration - Backfill existing rows in batches

    3. Migration 3 - Add NOT NULL constraint:
       migrations.AlterField(
           model_name='user',
           name='email',
           field=models.CharField(max_length=255, null=False),
       )
```

### Why It's Dangerous

When you add a NOT NULL column without a default:

1. **PostgreSQL:** Acquires `ACCESS EXCLUSIVE` lock on the table
2. **MySQL:** May rewrite the entire table depending on version
3. **During rewrite:** All other queries wait (reads AND writes)
4. **On large tables:** Can take minutes to hours

### The Safe Pattern

```python
# Migration 1: Add nullable field
migrations.AddField(
    model_name="user",
    name="email",
    field=models.CharField(max_length=255, null=True),
)

# Migration 2: Backfill data
def backfill_email(apps, schema_editor):
    User = apps.get_model('testapp', 'User')
    User.objects.filter(email__isnull=True).update(
        email='placeholder@example.com'
    )

migrations.RunPython(backfill_email, migrations.RunPython.noop)

# Migration 3: Add NOT NULL constraint
migrations.AlterField(
    model_name="user",
    name="email",
    field=models.CharField(max_length=255),
)
```

______________________________________________________________________

## Drop Column

**Rule:** SM002 | **Severity:** WARNING

### The Unsafe Pattern

```python
# testapp/migrations/0005_drop_column.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0004_unsafe_index"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="nickname",
        ),
    ]
```

### Tool Output

```
WARNING [SM002] testapp/migrations/0005_drop_column.py:17
  Dropping column 'nickname' from 'user' - ensure all code references have been removed first
  Operation: RemoveField(user.nickname)

  Suggestion:
    Safe column removal pattern:

    1. Deploy code that doesn't reference the column
    2. Wait for all servers to have new code
    3. Then run migration to drop column
```

### Why It's Dangerous

During rolling deployments:

```
Time    Event
0:00    Migration runs - column "nickname" deleted
0:01    Server A still running OLD code
0:02    Request hits Server A
0:02    Query: SELECT nickname FROM user WHERE...
0:02    ERROR: column "nickname" does not exist
0:05    Server A finally gets new code
```

### The Safe Pattern

1. **Deploy 1:** Remove all code references to the column
2. **Wait:** Ensure all servers have the new code
3. **Deploy 2:** Run the migration to drop the column

______________________________________________________________________

## Drop Table

**Rule:** SM003 | **Severity:** WARNING

### The Unsafe Pattern

```python
# testapp/migrations/0010_delete_model.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0009_run_python_no_reverse"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Profile",
        ),
    ]
```

### Tool Output

```
WARNING [SM003] testapp/migrations/0010_delete_model.py:17
  Dropping table 'profile' - ensure all code references have been removed first
  Operation: DeleteModel(Profile)

  Suggestion:
    Safe table removal pattern:

    1. Remove all code that references this model
    2. Deploy and verify no usage
    3. Then run migration to drop table
```

### Why It's Dangerous

Same as column drops, but worse:

- Entire model becomes inaccessible
- Foreign keys from other tables may fail
- Data loss is permanent

### The Safe Pattern

1. **Deploy 1:** Remove model from code, remove all FKs
2. **Wait:** Verify no queries hit the table (logs, monitoring)
3. **Deploy 2:** Drop the table

______________________________________________________________________

## Non-Concurrent Index (PostgreSQL)

**Rule:** SM010 | **Severity:** ERROR

### The Unsafe Pattern

```python
# testapp/migrations/0004_unsafe_index.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0003_safe_nullable"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
    ]
```

### Tool Output

```
ERROR [SM010] testapp/migrations/0004_unsafe_index.py:17
  Creating index without CONCURRENTLY on PostgreSQL will lock the table
  Operation: AddIndex(user, user_email_idx)

  Suggestion:
    Use AddIndexConcurrently from django.contrib.postgres.operations:

    from django.contrib.postgres.operations import AddIndexConcurrently

    class Migration(migrations.Migration):
        atomic = False  # Required for concurrent operations

        operations = [
            AddIndexConcurrently(
                model_name='user',
                index=models.Index(fields=['email'], name='user_email_idx'),
            ),
        ]
```

### Why It's Dangerous

Standard `CREATE INDEX`:

- Acquires `SHARE` lock on the table
- Blocks all `INSERT`, `UPDATE`, `DELETE` operations
- On large tables: minutes to hours of downtime

### The Safe Pattern

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # REQUIRED!

    operations = [
        AddIndexConcurrently(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
    ]
```

______________________________________________________________________

## RunSQL Without Reverse

**Rule:** SM007 | **Severity:** WARNING

### The Unsafe Pattern

```python
# testapp/migrations/0006_run_sql_no_reverse.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0005_drop_column"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX idx_user_created ON testapp_user (id)",
            # Missing reverse_sql!
        ),
    ]
```

### Tool Output

```
WARNING [SM007] testapp/migrations/0006_run_sql_no_reverse.py:17
  RunSQL without reverse_sql cannot be rolled back
  Operation: RunSQL(CREATE INDEX idx_user_created...)

  Suggestion:
    Add reverse_sql to make the migration reversible:

    migrations.RunSQL(
        sql="CREATE INDEX idx_user_created ON testapp_user (id)",
        reverse_sql="DROP INDEX IF EXISTS idx_user_created",
    )

    If the operation is intentionally irreversible, use:
    reverse_sql=migrations.RunSQL.noop
```

### Why It's Dangerous

- Cannot rollback if deployment fails
- Blocks automated rollback systems
- Makes debugging harder

### The Safe Pattern

```python
migrations.RunSQL(
    sql="CREATE INDEX idx_user_created ON testapp_user (id)",
    reverse_sql="DROP INDEX IF EXISTS idx_user_created",
)
```

______________________________________________________________________

## Enum Value in Transaction (PostgreSQL)

**Rule:** SM012 | **Severity:** ERROR

### The Unsafe Pattern

```python
# In an atomic migration (default)
class Migration(migrations.Migration):
    # atomic = True is the default

    operations = [
        migrations.RunSQL(
            sql="ALTER TYPE status_enum ADD VALUE 'pending'",
        ),
    ]
```

### Tool Output

```
ERROR [SM012] testapp/migrations/0007_enum_in_transaction.py:29
  ALTER TYPE ADD VALUE cannot run inside a transaction block in PostgreSQL
  Operation: RunSQL(ALTER TYPE...ADD VALUE...)

  Suggestion:
    Set atomic = False on the migration to run outside transaction:

    class Migration(migrations.Migration):
        atomic = False  # Required for ALTER TYPE ADD VALUE

        operations = [
            migrations.RunSQL(
                sql="ALTER TYPE status_enum ADD VALUE 'pending'",
                reverse_sql=migrations.RunSQL.noop,
            ),
        ]
```

### Why It's Dangerous

PostgreSQL does not allow `ALTER TYPE ... ADD VALUE` inside a transaction. The migration will fail with:

```
ERROR: ALTER TYPE ... ADD VALUE cannot run inside a transaction block
```

### The Safe Pattern

```python
class Migration(migrations.Migration):
    atomic = False  # REQUIRED!

    operations = [
        migrations.RunSQL(
            sql="ALTER TYPE status_enum ADD VALUE 'pending'",
            reverse_sql=migrations.RunSQL.noop,  # Cannot remove enum values
        ),
    ]
```

______________________________________________________________________

## Unique Constraint

**Rule:** SM009 | **Severity:** ERROR

### The Unsafe Pattern

```python
# testapp/migrations/0008_unique_constraint.py

class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0007_enum_in_transaction"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_user_email",
            ),
        ),
    ]
```

### Tool Output

```
ERROR [SM009] testapp/migrations/0008_unique_constraint.py:17
  Adding unique constraint requires full table scan to validate existing data
  Operation: AddConstraint(user, unique_user_email)

  Suggestion:
    For PostgreSQL, use AddConstraintNotValid + separate validation:

    1. Add constraint as NOT VALID (doesn't scan table):
       ALTER TABLE user ADD CONSTRAINT unique_user_email
       UNIQUE (email) NOT VALID;

    2. Validate in a separate migration:
       ALTER TABLE user VALIDATE CONSTRAINT unique_user_email;
```

### Why It's Dangerous

Adding a unique constraint:

1. Scans the entire table to check for duplicates
2. Holds locks during the scan
3. On large tables: significant downtime

### The Safe Pattern (PostgreSQL)

```python
class Migration(migrations.Migration):
    atomic = False

    operations = [
        # Step 1: Create unique index concurrently
        AddIndexConcurrently(
            model_name="user",
            index=models.Index(
                fields=["email"],
                name="unique_user_email_idx",
            ),
        ),
        # Step 2: Add constraint using the index
        migrations.RunSQL(
            sql="""
            ALTER TABLE testapp_user
            ADD CONSTRAINT unique_user_email
            UNIQUE USING INDEX unique_user_email_idx;
            """,
            reverse_sql="ALTER TABLE testapp_user DROP CONSTRAINT unique_user_email;",
        ),
    ]
```

______________________________________________________________________

## RunPython Without Reverse

**Rule:** SM016 | **Severity:** INFO

### The Unsafe Pattern

```python
# testapp/migrations/0009_run_python_no_reverse.py

def populate_data(apps, schema_editor):
    """Populate some data."""
    User = apps.get_model('testapp', 'User')
    User.objects.create(name="Default User")


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0008_unique_constraint"),
    ]

    operations = [
        migrations.RunPython(
            populate_data,
            # Missing reverse_code!
        ),
    ]
```

### Tool Output

```
INFO [SM016] testapp/migrations/0009_run_python_no_reverse.py:22
  RunPython without reverse_code cannot be rolled back
  Operation: RunPython(populate_data)

  Suggestion:
    Add reverse_code to make the migration reversible:

    def reverse_populate(apps, schema_editor):
        User = apps.get_model('testapp', 'User')
        User.objects.filter(name="Default User").delete()

    migrations.RunPython(
        populate_data,
        reverse_code=reverse_populate,
    )

    If intentionally irreversible, use:
    reverse_code=migrations.RunPython.noop
```

### Why It Matters

- Prevents rollback in case of failed deployment
- Makes testing migrations harder
- Can block CI/CD pipelines that test rollbacks

### The Safe Pattern

```python
def populate_data(apps, schema_editor):
    User = apps.get_model('testapp', 'User')
    User.objects.create(name="Default User")


def reverse_populate(apps, schema_editor):
    User = apps.get_model('testapp', 'User')
    User.objects.filter(name="Default User").delete()


class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(
            populate_data,
            reverse_code=reverse_populate,
        ),
    ]
```

______________________________________________________________________

## 32-bit Primary Key

**Rule:** SM028 | **Severity:** WARNING

### The Unsafe Pattern

```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='order',
            name='id',
            field=models.AutoField(primary_key=True),
        ),
    ]
```

### Tool Output

```
WARNING [SM028] myapp/migrations/0021_autofield.py
  Prefer BigAutoField over 32-bit AutoField for primary keys.
  32-bit integers max out at ~2.1 billion rows.
```

### Why It's Dangerous

Using a 32-bit `AutoField` limits your table to approximately 2.1 billion rows. While that sounds like a lot, high-write tables (logs, events, orders) can hit this ceiling, causing inserts to fail with integer overflow errors. Migrating a large table from `AutoField` to `BigAutoField` later requires a full table rewrite, which means extended downtime.

### The Safe Pattern

```python
# settings.py
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

______________________________________________________________________

## Non-Concurrent Index Removal (PostgreSQL)

**Rule:** SM030 | **Severity:** ERROR

### The Unsafe Pattern

```python
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveIndex(
            model_name='order',
            name='order_status_idx',
        ),
    ]
```

### Tool Output

```
ERROR [SM030] myapp/migrations/0023_remove_index.py
  Index removal without CONCURRENTLY will lock the table on PostgreSQL.
```

### Why It's Dangerous

Standard `DROP INDEX`:

- Acquires `ACCESS EXCLUSIVE` lock on the table
- Blocks all reads and writes while the index is being removed
- On large tables with many concurrent connections, this can cause request queuing and timeouts

### The Safe Pattern

```python
from django.contrib.postgres.operations import RemoveIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # REQUIRED for concurrent operations

    operations = [
        RemoveIndexConcurrently(
            model_name='order',
            name='order_status_idx',
        ),
    ]
```

______________________________________________________________________

## NOT NULL Field with Python Default

**Rule:** SM033 | **Severity:** WARNING

### The Unsafe Pattern

```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='order',
            name='status',
            field=models.CharField(max_length=20, default='pending'),
        ),
    ]
```

### Tool Output

```
WARNING [SM033] myapp/migrations/0025_add_status.py
  Adding NOT NULL field with Python default rewrites all existing rows.
```

### Why It's Dangerous

When you add a NOT NULL column with a Python-level `default`:

1. Django generates SQL that adds the column with a server-side DEFAULT
2. PostgreSQL then rewrites every existing row to fill in the default value
3. This acquires an `ACCESS EXCLUSIVE` lock for the duration of the rewrite
4. On large tables, the rewrite can take minutes to hours, blocking all queries

### The Safe Pattern

```python
# Django 5.0+: Use db_default to set the default at the database level
# without rewriting existing rows on supported databases
migrations.AddField(
    model_name='order',
    name='status',
    field=models.CharField(max_length=20, db_default='pending'),
)
```

______________________________________________________________________

## Missing lock_timeout in RunSQL

**Rule:** SM035 | **Severity:** INFO

### The Unsafe Pattern

```python
class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE myapp_order ADD COLUMN priority INTEGER DEFAULT 0;",
        ),
    ]
```

### Tool Output

```
INFO [SM035] myapp/migrations/0026_alter_order.py
  RunSQL with DDL should set lock_timeout to avoid blocking.
```

### Why It Matters

DDL statements like `ALTER TABLE` acquire locks that can block other queries. Without a `lock_timeout`, if the lock cannot be acquired immediately (because of long-running queries holding conflicting locks), the migration will wait indefinitely, which in turn queues up all subsequent queries behind it, potentially causing a full outage.

### The Safe Pattern

```python
migrations.RunSQL(
    sql=[
        "SET lock_timeout = '5s';",
        "ALTER TABLE myapp_order ADD COLUMN priority INTEGER DEFAULT 0;",
    ],
    reverse_sql="ALTER TABLE myapp_order DROP COLUMN priority;",
)
```

______________________________________________________________________

## Running the Examples

You can test these patterns yourself by running django-safe-migrations against our test suite:

```bash
# Clone the repository
git clone https://github.com/YasserShkeir/django-safe-migrations.git
cd django-safe-migrations

# Install in development mode
pip install -e ".[dev]"

# Run against test migrations
cd tests/test_project
python manage.py check_migrations testapp
```

You should see output detecting all the unsafe patterns documented above.

## See Also

- [Rules Reference](rules/index.md) - Detailed documentation for each rule
- [Safe Patterns](patterns.md) - Comprehensive guide to safe migration patterns
- [Configuration](configuration.md) - How to suppress or configure rules
