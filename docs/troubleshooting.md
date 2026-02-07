# Troubleshooting

This guide covers common issues, false positives, and edge cases when using django-safe-migrations.

## False Positives

### SM001: NOT NULL Without Default

**Scenario**: You're adding a NOT NULL field but have already backfilled data.

```python
# Migration 1: Add nullable field
migrations.AddField(
    model_name='user',
    name='email',
    field=models.EmailField(null=True),
)

# Migration 2: Backfill data (RunPython)

# Migration 3: Make NOT NULL - FLAGGED as SM001
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.EmailField(null=False),
)
```

**Solution**: Suppress the rule with an explanation:

```python
# safe-migrations: ignore SM001 -- backfilled in migration 0002
migrations.AlterField(...)
```

### SM010: Non-Concurrent Index on Small Table

**Scenario**: You're creating an index on a small lookup table.

**Solution**: If you're certain the table is small:

```python
# safe-migrations: ignore SM010 -- lookup table with < 1000 rows
migrations.AddIndex(
    model_name='country',
    index=models.Index(fields=['code'], name='country_code_idx'),
)
```

### SM020: AlterField null=False on New Table

**Scenario**: You're setting null=False on a table that was just created (no existing rows).

**Solution**: Suppress with context:

```python
# safe-migrations: ignore SM020 -- table created in same release, no data yet
migrations.AlterField(...)
```

## Configuration Issues

### "Unknown rule ID" Warnings

**Symptom**: Warnings about unknown rule IDs in your configuration.

```
WARNING: Unknown rule ID 'SM099' in DISABLED_RULES. Did you mean 'SM009'?
```

**Cause**: Typo in rule ID or using a rule from a newer version.

**Solution**: Check available rules:

```bash
python manage.py check_migrations --list-rules
```

### "Unknown category" Warnings

**Symptom**: Warnings about unknown categories.

```
WARNING: Unknown category 'destrutive' in DISABLED_CATEGORIES. Did you mean 'destructive'?
```

**Solution**: Use the correct category name. Valid categories:

- `postgresql`, `indexes`, `constraints`, `destructive`
- `locking`, `data-loss`, `reversibility`, `data-migrations`
- `high-risk`, `informational`, `naming`, `schema-changes`
- `relations`, `security`, `performance`

### Rules Not Being Detected

**Symptom**: A rule you expect to trigger isn't being reported.

**Possible causes**:

1. **Rule is disabled**: Check `DISABLED_RULES` and `DISABLED_CATEGORIES`
2. **Database-specific rule**: Some rules only apply to PostgreSQL
3. **App is excluded**: Check `EXCLUDED_APPS` setting
4. **Suppression comment**: Look for `# safe-migrations: ignore` in the migration

**Debug steps**:

```bash
# List all active rules
python manage.py check_migrations --list-rules --format=json | python -c "
import json, sys
rules = json.load(sys.stdin)
for r in rules:
    print(f\"{r['rule_id']}: {r['description']} (db: {r['db_vendors']})\")
"

# Check specific app
python manage.py check_migrations myapp --format=json
```

### Custom Rules Not Loading

**Symptom**: Your `EXTRA_RULES` custom rules aren't being applied.

**Checklist**:

1. **Import path is correct**: Use fully qualified dotted path

   ```python
   # Correct
   "myapp.migration_rules.MyRule"

   # Wrong
   "MyRule"
   "migration_rules.MyRule"
   ```

2. **Class inherits from BaseRule**:

   ```python
   from django_safe_migrations.rules.base import BaseRule

   class MyRule(BaseRule):  # Must inherit BaseRule
       ...
   ```

3. **Required attributes are defined**:

   ```python
   class MyRule(BaseRule):
       rule_id = "CUSTOM001"  # Required
       severity = Severity.WARNING  # Required
       description = "My rule"  # Required

       def check(self, operation, migration, **kwargs):  # Required
           ...
   ```

4. **Check for import errors**:

   ```python
   # In Django shell
   from django.utils.module_loading import import_string
   import_string("myapp.migration_rules.MyRule")
   ```

## Database-Specific Issues

### PostgreSQL Rules on SQLite

**Symptom**: Rules like SM010, SM011, SM018 aren't triggering.

**Cause**: These rules have `db_vendors = ["postgresql"]` and only run on PostgreSQL.

**Solution**: This is expected behavior. Run tests against PostgreSQL to see these rules:

```bash
# Using Docker
docker-compose -f docker-compose.test.yml up test-py313
```

### MySQL Compatibility

**Symptom**: Some rules behave differently on MySQL.

**Note**: Most rules are designed for PostgreSQL. MySQL has different locking behavior and some rules may not apply. Consider:

- SM010 (concurrent index) - MySQL doesn't support `CONCURRENTLY`
- SM012 (enum in transaction) - PostgreSQL-specific
- SM018 (concurrent in atomic) - PostgreSQL-specific

## CI/CD Issues

### Exit Code Always 0

**Symptom**: CI pipeline doesn't fail when issues are found.

**Cause**: Only ERROR severity issues cause exit code 1. Warnings don't.

**Solution**: Use `--fail-on-warning`:

```bash
python manage.py check_migrations --fail-on-warning
```

### GitHub Actions Annotations Not Showing

**Symptom**: Using `--format=github` but no annotations appear.

**Checklist**:

1. Output must go to stdout (default)
2. Check GitHub Actions logs for `::error` or `::warning` lines
3. Ensure the step isn't failing before output is processed

```yaml
- name: Check migrations
  run: python manage.py check_migrations --format=github
  continue-on-error: false
```

### SARIF Upload Failing

**Symptom**: GitHub code scanning upload fails.

**Solution**: Ensure valid SARIF output:

```yaml
- name: Check migrations
  run: |
    python manage.py check_migrations --format=sarif --output=results.sarif
  continue-on-error: true # Don't fail before upload

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

## Performance Issues

### Slow Analysis on Large Codebases

**Symptom**: `check_migrations` takes a long time.

**Solutions**:

1. **Exclude apps you don't control**:

   ```python
   SAFE_MIGRATIONS = {
       "EXCLUDED_APPS": [
           "django_celery_beat",
           "allauth",
           "rest_framework",
       ],
   }
   ```

2. **Check only new migrations**:

   ```bash
   python manage.py check_migrations --new-only
   ```

3. **Check specific apps**:

   ```bash
   python manage.py check_migrations myapp otherapp
   ```

### Memory Issues with Large Migrations

**Symptom**: Out of memory when analyzing migrations with large data operations.

**Note**: This is usually caused by the migration itself, not the analyzer. The SM026 rule specifically detects this pattern:

```python
# Bad - loads all rows into memory
for obj in Model.objects.all():
    ...

# Good - uses iterator
for obj in Model.objects.all().iterator(chunk_size=1000):
    ...
```

## Common Error Messages

### "Could not configure Django"

```
Error: Could not configure Django. Please set DJANGO_SETTINGS_MODULE environment variable.
```

**Solution**:

```bash
export DJANGO_SETTINGS_MODULE=myproject.settings
python -m django_safe_migrations myapp
```

Or use `manage.py`:

```bash
python manage.py check_migrations myapp
```

### "No migrations found"

**Cause**: App has no migrations or app label is incorrect.

**Solution**:

```bash
# Check app exists
python manage.py showmigrations myapp

# Create migrations if needed
python manage.py makemigrations myapp
```

### "Migration has no operations"

**Cause**: Empty migration file (possibly auto-generated merge migration).

**Note**: This is usually fine - empty migrations are valid Django migrations.

## Getting Help

If you encounter an issue not covered here:

1. **Check existing issues**: [GitHub Issues](https://github.com/YasserShkeir/django-safe-migrations/issues)
2. **Search discussions**: Look for similar problems
3. **Open a new issue**: Include:
   - django-safe-migrations version
   - Django version
   - Python version
   - Database backend
   - Minimal reproduction case
   - Full error message/traceback

## Baseline and Diff Mode

### Baseline file not found

```
FileNotFoundError: [Errno 2] No such file or directory: '.migration-baseline.json'
```

**Solution:** Generate the baseline first:

```bash
python manage.py check_migrations --generate-baseline .migration-baseline.json
```

### Diff mode shows no changes

If `--diff` reports no changed migrations:

1. Ensure you're comparing against the correct branch: `--diff main` or `--diff origin/main`
2. Check that the migration files actually exist on disk (deleted files are filtered out)
3. Verify git can run: `git diff --name-only main`

### Watch mode not starting

```
ImportError: watchdog is required for watch mode
```

**Solution:** Install the watch extra:

```bash
pip install django-safe-migrations[watch]
```

### Interactive mode not working in CI

Interactive mode requires a terminal for user input. Do not use `--interactive` in CI pipelines.

## See Also

- [Configuration](configuration.md) - All configuration options
- [Custom Rules](custom-rules.md) - Writing your own rules
- [Rules Reference](rules.md) - All built-in rules
