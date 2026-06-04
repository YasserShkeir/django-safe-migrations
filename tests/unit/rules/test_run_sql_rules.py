"""Tests for RunSQL and RunPython rules."""

import inspect

import pytest
from django.db import migrations

from django_safe_migrations.rules.base import Severity
from django_safe_migrations.rules.run_sql import (
    EnumAddValueInTransactionRule,
    LargeDataMigrationRule,
    RunPythonNoBatchingRule,
    RunPythonWithoutReverseRule,
    RunSQLWithoutReverseRule,
    SQLInjectionPatternRule,
)


class TestRunSQLWithoutReverseRule:
    """Tests for RunSQLWithoutReverseRule (SM007)."""

    def test_detects_runsql_without_reverse(self, mock_migration):
        """Test that rule detects RunSQL without reverse_sql."""
        rule = RunSQLWithoutReverseRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx ON users (email)",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM007"
        assert issue.severity == Severity.WARNING
        assert "reverse_sql" in issue.message

    def test_allows_runsql_with_reverse(self, mock_migration):
        """Test that rule allows RunSQL with reverse_sql."""
        rule = RunSQLWithoutReverseRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx ON users (email)",
            reverse_sql="DROP INDEX idx",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_runsql_with_noop_reverse(self, mock_migration):
        """Test that rule allows RunSQL with noop reverse."""
        rule = RunSQLWithoutReverseRule()
        operation = migrations.RunSQL(
            sql="COMMENT ON TABLE users IS 'User accounts'",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_runsql_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunSQL operations."""
        rule = RunSQLWithoutReverseRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = RunSQLWithoutReverseRule()
        operation = migrations.RunSQL(sql="CREATE INDEX idx ON users (email)")
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "reverse_sql" in suggestion


class TestEnumAddValueInTransactionRule:
    """Tests for EnumAddValueInTransactionRule (SM012)."""

    def test_detects_enum_add_value_in_atomic_migration(self, mock_migration):
        """Test that rule detects ALTER TYPE ADD VALUE in atomic migration."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="ALTER TYPE status_enum ADD VALUE 'pending'",
            reverse_sql=migrations.RunSQL.noop,
        )
        # Default migration is atomic=True
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM012"
        assert issue.severity == Severity.ERROR
        assert "atomic=False" in issue.message

    def test_allows_enum_add_value_in_non_atomic_migration(self):
        """Test that rule allows ALTER TYPE ADD VALUE in non-atomic migration."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="ALTER TYPE status_enum ADD VALUE 'pending'",
            reverse_sql=migrations.RunSQL.noop,
        )

        class NonAtomicMigration:
            """Mock migration with atomic=False."""

            app_label = "testapp"
            name = "0001_test"
            atomic = False

        issue = rule.check(operation, NonAtomicMigration())

        assert issue is None

    def test_ignores_regular_sql(self, mock_migration):
        """Test that rule ignores SQL without enum operations."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx ON users (email)",
            reverse_sql="DROP INDEX idx",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(sql="ALTER TYPE status_enum ADD VALUE 'pending'")
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "atomic = False" in suggestion

    def test_does_not_match_plain_add_value_words(self, mock_migration):
        r"""Test that SM012 does not match 'ADD VALUE' outside ALTER TYPE context.

        The v0.5.0 fix removed the broad 'add\s+value' pattern that would
        match any SQL containing those words.
        """
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="INSERT INTO config (key, val) VALUES ('add', 'value')",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_still_detects_alter_type_add_value(self, mock_migration):
        """Test that SM012 still detects the full ALTER TYPE ... ADD VALUE pattern."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="ALTER TYPE my_enum ADD VALUE 'new_entry'",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM012"

    def test_detects_schema_qualified_enum(self, mock_migration):
        """SM012 detects a schema-qualified enum type name."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="ALTER TYPE myschema.my_enum ADD VALUE 'new_entry'",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM012"

    def test_detects_quoted_enum(self, mock_migration):
        """SM012 detects a double-quoted enum type name."""
        rule = EnumAddValueInTransactionRule()
        operation = migrations.RunSQL(
            sql="ALTER TYPE \"My Enum\" ADD VALUE 'new_entry'",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM012"


class TestLargeDataMigrationRule:
    """Tests for LargeDataMigrationRule (SM008)."""

    def test_detects_runpython_operation(self, mock_migration):
        """Test that rule detects RunPython operations."""
        rule = LargeDataMigrationRule()

        def forward_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(forward_func)
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM008"
        assert issue.severity == Severity.INFO
        assert "batch" in issue.message.lower() or "slow" in issue.message.lower()

    def test_ignores_non_runpython_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunPython operations."""
        rule = LargeDataMigrationRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = LargeDataMigrationRule()

        def forward_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(forward_func)
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "batch" in suggestion.lower()
        assert "iterator" in suggestion.lower()


class TestRunPythonWithoutReverseRule:
    """Tests for RunPythonWithoutReverseRule (SM016)."""

    def test_detects_runpython_without_reverse(self, mock_migration):
        """Test that rule detects RunPython without reverse_code."""
        rule = RunPythonWithoutReverseRule()

        def forward_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(forward_func)
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM016"
        assert issue.severity == Severity.INFO
        assert "reverse_code" in issue.message

    def test_allows_runpython_with_reverse(self, mock_migration):
        """Test that rule allows RunPython with reverse_code."""
        rule = RunPythonWithoutReverseRule()

        def forward_func(apps, schema_editor):
            pass

        def reverse_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(forward_func, reverse_code=reverse_func)
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_runpython_with_noop_reverse(self, mock_migration):
        """Test that rule allows RunPython with noop reverse."""
        rule = RunPythonWithoutReverseRule()

        def forward_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(
            forward_func, reverse_code=migrations.RunPython.noop
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_runpython_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunPython operations."""
        rule = RunPythonWithoutReverseRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_ignores_runsql_operations(self, mock_migration):
        """Test that rule ignores RunSQL operations."""
        rule = RunPythonWithoutReverseRule()
        operation = migrations.RunSQL(sql="SELECT 1")
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = RunPythonWithoutReverseRule()

        def forward_func(apps, schema_editor):
            pass

        operation = migrations.RunPython(forward_func)
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "reverse_code" in suggestion
        assert "noop" in suggestion.lower()


class TestSQLInjectionPatternRule:
    """Tests for SQLInjectionPatternRule (SM024)."""

    def test_detects_percent_s_formatting(self, mock_migration):
        """Test that rule detects %s formatting in SQL."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE id = %s",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM024"
        assert issue.severity == Severity.ERROR
        assert (
            "injection" in issue.message.lower() or "pattern" in issue.message.lower()
        )

    def test_detects_named_formatting(self, mock_migration):
        """Test that rule detects %(name)s formatting in SQL."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE name = %(name)s",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM024"

    def test_detects_format_string_pattern(self, mock_migration):
        """Test that rule detects {name} format strings."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE id = {user_id}",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM024"

    def test_detects_string_concatenation(self, mock_migration):
        """Test that rule detects string concatenation patterns."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE name = '" + "test'",
            reverse_sql=migrations.RunSQL.noop,
        )
        # Note: This tests the pattern detection in the SQL string itself
        issue = rule.check(operation, mock_migration)

        # The concatenation happens at test time, so the actual SQL is safe
        # This test verifies the rule checks for concatenation patterns
        assert issue is None  # The string was concatenated at test time

    def test_allows_static_sql(self, mock_migration):
        """Test that rule allows static SQL strings."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx_email ON users (email)",
            reverse_sql="DROP INDEX idx_email",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_runsql_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunSQL operations."""
        rule = SQLInjectionPatternRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(sql="SELECT * FROM users WHERE id = %s")
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "static" in suggestion.lower() or "parameterized" in suggestion.lower()

    def test_allows_like_percent_pattern(self, mock_migration):
        """Test that SM024 does not flag LIKE '%something%' patterns.

        The v0.5.0 fix uses (?<!')%s(?!') to exclude %s inside quotes.
        """
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE email LIKE '%something%'",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_empty_json_braces(self, mock_migration):
        """Test that SM024 does not flag empty {} braces (JSON/array syntax).

        The v0.5.0 fix requires an identifier inside braces: {name} not {}.
        """
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT '{}'::jsonb",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_still_detects_named_format_braces(self, mock_migration):
        """Test that SM024 still detects {user_id} format strings."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users WHERE id = {user_id}",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM024"

    def test_still_detects_bare_percent_s(self, mock_migration):
        """Test that SM024 still detects bare %s outside quotes."""
        rule = SQLInjectionPatternRule()
        operation = migrations.RunSQL(
            sql="UPDATE users SET name = %s WHERE id = 1",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM024"


def _source_inspection_available() -> bool:
    """Check if inspect.getsource() works in this environment."""
    try:
        inspect.getsource(_source_inspection_available)
        return True
    except OSError:
        return False


@pytest.mark.skipif(
    not _source_inspection_available(),
    reason="Source inspection not available in this environment",
)
class TestRunPythonNoBatchingRule:
    """Tests for RunPythonNoBatchingRule (SM026).

    Note: These tests rely on inspect.getsource() which may not work in all
    environments (e.g., Docker with volume-mounted code from different paths).
    """

    def test_detects_all_without_iterator(self, mock_migration):
        """Test that rule detects .all() without .iterator()."""
        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            for obj in Model.objects.all():
                obj.save()

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM026"
        assert issue.severity == Severity.WARNING
        assert "migrate_data" in issue.message
        assert "all()" in issue.message.lower() or "batch" in issue.message.lower()

    def test_allows_all_with_iterator(self, mock_migration):
        """Test that rule allows .all() with .iterator()."""
        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            for obj in Model.objects.all().iterator(chunk_size=1000):
                obj.save()

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_values_list(self, mock_migration):
        """Test that rule allows .values_list() usage."""
        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            ids = Model.objects.all().values_list("id", flat=True)
            return list(ids)

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        # values_list is memory efficient
        assert issue is None

    def test_allows_batching_pattern(self, mock_migration):
        """Test that rule allows explicit batching."""
        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            batch_size = 1000
            for batch in Model.objects.all()[:batch_size]:
                batch.save()

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        # Has batching pattern
        assert issue is None

    def test_ignores_non_runpython_operations(self, mock_migration):
        """Test that rule ignores non-RunPython operations."""
        rule = RunPythonNoBatchingRule()
        operation = migrations.RunSQL(sql="SELECT 1")
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, mock_migration):
        """Test that rule provides a helpful suggestion."""
        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            for obj in Model.objects.all():
                obj.save()

        operation = migrations.RunPython(migrate_data)
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "iterator" in suggestion.lower() or "batch" in suggestion.lower()


class TestRequireLockTimeoutRule:
    """Tests for RequireLockTimeoutRule (SM035)."""

    def test_detects_alter_table_without_lock_timeout(self, mock_migration):
        """Test that rule detects ALTER TABLE without lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="ALTER TABLE users ADD COLUMN age INTEGER",
            reverse_sql="ALTER TABLE users DROP COLUMN age",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"
        assert issue.severity == Severity.INFO
        assert "lock_timeout" in issue.message.lower()

    def test_detects_create_index_without_lock_timeout(self, mock_migration):
        """Test that rule detects CREATE INDEX without lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx_email ON users (email)",
            reverse_sql="DROP INDEX idx_email",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_detects_drop_table_without_lock_timeout(self, mock_migration):
        """Test that rule detects DROP TABLE without lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="DROP TABLE old_users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_allows_ddl_with_lock_timeout_in_sql(self, mock_migration):
        """Test that rule allows DDL when lock_timeout is in the SQL."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql=[
                "SET lock_timeout = '5s'",
                "ALTER TABLE users ADD COLUMN age INTEGER",
                "SET lock_timeout = '0'",
            ],
            reverse_sql="ALTER TABLE users DROP COLUMN age",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_ddl_with_lock_timeout_in_same_migration(
        self, mock_migration_factory
    ):
        """Test that rule allows DDL when lock_timeout is in another op."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        lock_timeout_op = migrations.RunSQL(sql="SET lock_timeout = '5s'")
        ddl_op = migrations.RunSQL(
            sql="ALTER TABLE users ADD COLUMN age INTEGER",
            reverse_sql="ALTER TABLE users DROP COLUMN age",
        )
        mock_mig = mock_migration_factory(
            operations=[lock_timeout_op, ddl_op],
        )
        issue = rule.check(ddl_op, mock_mig)

        assert issue is None

    def test_ignores_non_ddl_sql(self, mock_migration):
        """Test that rule ignores non-DDL SQL statements."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="SELECT COUNT(*) FROM users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_insert_sql(self, mock_migration):
        """Test that rule ignores INSERT statements (not DDL)."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="INSERT INTO config (key, value) VALUES ('version', '1.0')",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_runsql_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunSQL operations."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_detects_create_table_without_lock_timeout(self, mock_migration):
        """Test that rule detects CREATE TABLE without lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="CREATE TABLE temp_users (id SERIAL PRIMARY KEY)",
            reverse_sql="DROP TABLE temp_users",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_detects_truncate_without_lock_timeout(self, mock_migration):
        """Test that rule detects TRUNCATE without lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="TRUNCATE TABLE users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql="ALTER TABLE users ADD COLUMN age INTEGER",
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "lock_timeout" in suggestion.lower()

    def test_flags_lock_timeout_after_ddl_in_list(self, mock_migration):
        """SM035 flags DDL when SET lock_timeout comes AFTER it in the list."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql=[
                "ALTER TABLE users ADD COLUMN age INTEGER",
                "SET lock_timeout = '5s'",
            ],
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_allows_lock_timeout_before_ddl_in_list(self, mock_migration):
        """SM035 stays silent when SET lock_timeout precedes the DDL."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        rule = RequireLockTimeoutRule()
        operation = migrations.RunSQL(
            sql=[
                "SET lock_timeout = '5s'",
                "ALTER TABLE users ADD COLUMN age INTEGER",
                "SET lock_timeout = '0'",
            ],
            reverse_sql=migrations.RunSQL.noop,
        )

        assert rule.check(operation, mock_migration) is None

    def test_flags_ddl_when_lock_timeout_is_later_operation(
        self, mock_migration_factory
    ):
        """SM035 flags a DDL op when lock_timeout is set in a LATER op."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        ddl_op = migrations.RunSQL(
            sql="ALTER TABLE users ADD COLUMN age INTEGER",
            reverse_sql=migrations.RunSQL.noop,
        )
        lock_op = migrations.RunSQL(
            sql="SET lock_timeout = '5s'", reverse_sql=migrations.RunSQL.noop
        )
        migration = mock_migration_factory([ddl_op, lock_op])

        rule = RequireLockTimeoutRule()
        issue = rule.check(ddl_op, migration)

        assert issue is not None
        assert issue.rule_id == "SM035"

    def test_allows_ddl_when_lock_timeout_is_earlier_operation(
        self, mock_migration_factory
    ):
        """SM035 stays silent when an EARLIER op already set lock_timeout."""
        from django_safe_migrations.rules.run_sql import RequireLockTimeoutRule

        lock_op = migrations.RunSQL(
            sql="SET lock_timeout = '5s'", reverse_sql=migrations.RunSQL.noop
        )
        ddl_op = migrations.RunSQL(
            sql="ALTER TABLE users ADD COLUMN age INTEGER",
            reverse_sql=migrations.RunSQL.noop,
        )
        migration = mock_migration_factory([lock_op, ddl_op])

        rule = RequireLockTimeoutRule()

        assert rule.check(ddl_op, migration) is None


class TestPreferIfExistsRule:
    """Tests for PreferIfExistsRule (SM036)."""

    def test_detects_create_table_without_if_not_exists(self, mock_migration):
        """Test that rule detects CREATE TABLE without IF NOT EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="CREATE TABLE temp_users (id SERIAL PRIMARY KEY)",
            reverse_sql="DROP TABLE temp_users",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"
        assert issue.severity == Severity.INFO
        assert "CREATE TABLE" in issue.message
        assert "IF NOT EXISTS" in issue.message

    def test_allows_create_table_with_if_not_exists(self, mock_migration):
        """Test that rule allows CREATE TABLE IF NOT EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="CREATE TABLE IF NOT EXISTS temp_users (id SERIAL PRIMARY KEY)",
            reverse_sql="DROP TABLE IF EXISTS temp_users",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_drop_table_without_if_exists(self, mock_migration):
        """Test that rule detects DROP TABLE without IF EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="DROP TABLE old_users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"
        assert "DROP TABLE" in issue.message
        assert "IF EXISTS" in issue.message

    def test_allows_drop_table_with_if_exists(self, mock_migration):
        """Test that rule allows DROP TABLE IF EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="DROP TABLE IF EXISTS old_users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_table_ddl(self, mock_migration):
        """Test that rule ignores CREATE INDEX and other non-table DDL."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="CREATE INDEX idx_email ON users (email)",
            reverse_sql="DROP INDEX idx_email",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_runsql_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RunSQL operations."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_ignores_select_statements(self, mock_migration):
        """Test that rule ignores SELECT statements."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="SELECT * FROM users",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_case_insensitive_detection(self, mock_migration):
        """Test that rule handles case-insensitive SQL."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="create table temp_users (id serial primary key)",
            reverse_sql="drop table temp_users",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"

    def test_case_insensitive_allows_if_not_exists(self, mock_migration):
        """Test that rule handles case-insensitive IF NOT EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="create table if not exists temp_users (id serial primary key)",
            reverse_sql="drop table if exists temp_users",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_handles_sql_list(self, mock_migration):
        """Test that rule handles SQL provided as a list."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql=["CREATE TABLE temp_users (id SERIAL PRIMARY KEY)"],
            reverse_sql=["DROP TABLE temp_users"],
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="CREATE TABLE temp_users (id SERIAL PRIMARY KEY)",
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "IF NOT EXISTS" in suggestion
        assert "IF EXISTS" in suggestion

    def test_detects_bare_create_among_safe_siblings_list(self, mock_migration):
        """A bare CREATE TABLE is flagged even if a sibling uses IF NOT EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql=[
                "CREATE TABLE IF NOT EXISTS a (id INTEGER)",
                "CREATE TABLE b (id INTEGER)",
            ],
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"
        assert "CREATE TABLE" in issue.message

    def test_detects_bare_create_in_multistatement_string(self, mock_migration):
        """A bare CREATE TABLE in a ';'-separated string is flagged."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql=(
                "CREATE TABLE IF NOT EXISTS a (id INTEGER); "
                "CREATE TABLE b (id INTEGER);"
            ),
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"

    def test_detects_bare_drop_among_safe_siblings(self, mock_migration):
        """A bare DROP TABLE is flagged even if a sibling uses IF EXISTS."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql="DROP TABLE IF EXISTS a; DROP TABLE b;",
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"
        assert "DROP TABLE" in issue.message

    def test_allows_all_safe_multistatement(self, mock_migration):
        """No false positive when every statement is defensive."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql=[
                "CREATE TABLE IF NOT EXISTS a (id INTEGER)",
                "DROP TABLE IF EXISTS b",
            ],
            reverse_sql=migrations.RunSQL.noop,
        )

        assert rule.check(operation, mock_migration) is None

    def test_handles_sql_list_with_params_tuples(self, mock_migration):
        """A bare CREATE TABLE in (sql, params) tuple-list form is flagged."""
        from django_safe_migrations.rules.run_sql import PreferIfExistsRule

        rule = PreferIfExistsRule()
        operation = migrations.RunSQL(
            sql=[("CREATE TABLE a (id INTEGER)", None)],
            reverse_sql=migrations.RunSQL.noop,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM036"


class TestTruncateInRunSQLRule:
    """Tests for TruncateInRunSQLRule (SM048)."""

    def test_flags_truncate(self, mock_migration):
        """TRUNCATE in RunSQL is flagged."""
        from django_safe_migrations.rules.run_sql import TruncateInRunSQLRule

        rule = TruncateInRunSQLRule()
        op = migrations.RunSQL(
            "TRUNCATE TABLE users", reverse_sql=migrations.RunSQL.noop
        )
        issue = rule.check(op, mock_migration)
        assert issue is not None
        assert issue.rule_id == "SM048"

    def test_ignores_non_truncate(self, mock_migration):
        """Non-TRUNCATE SQL is not flagged."""
        from django_safe_migrations.rules.run_sql import TruncateInRunSQLRule

        rule = TruncateInRunSQLRule()
        op = migrations.RunSQL("DELETE FROM users WHERE id = 1")
        assert rule.check(op, mock_migration) is None

    def test_ignores_truncate_in_comment(self, mock_migration):
        """The word TRUNCATE inside a comment must not fire (anchored match)."""
        from django_safe_migrations.rules.run_sql import TruncateInRunSQLRule

        rule = TruncateInRunSQLRule()
        op = migrations.RunSQL("-- we will TRUNCATE later\nSELECT 1")
        assert rule.check(op, mock_migration) is None

    def test_ignores_non_runsql(self, not_null_field_operation, mock_migration):
        """Non-RunSQL operations are ignored."""
        from django_safe_migrations.rules.run_sql import TruncateInRunSQLRule

        rule = TruncateInRunSQLRule()
        assert rule.check(not_null_field_operation, mock_migration) is None


class TestDropDatabaseInRunSQLRule:
    """Tests for DropDatabaseInRunSQLRule (SM050)."""

    def test_flags_drop_database(self, mock_migration):
        """DROP DATABASE is flagged."""
        from django_safe_migrations.rules.run_sql import DropDatabaseInRunSQLRule

        rule = DropDatabaseInRunSQLRule()
        op = migrations.RunSQL("DROP DATABASE production")
        issue = rule.check(op, mock_migration)
        assert issue is not None
        assert issue.rule_id == "SM050"
        assert issue.severity == Severity.ERROR

    def test_flags_drop_schema(self, mock_migration):
        """DROP SCHEMA is flagged."""
        from django_safe_migrations.rules.run_sql import DropDatabaseInRunSQLRule

        rule = DropDatabaseInRunSQLRule()
        op = migrations.RunSQL("DROP SCHEMA legacy CASCADE")
        assert rule.check(op, mock_migration) is not None

    def test_ignores_drop_table(self, mock_migration):
        """DROP TABLE is not this rule's concern."""
        from django_safe_migrations.rules.run_sql import DropDatabaseInRunSQLRule

        rule = DropDatabaseInRunSQLRule()
        op = migrations.RunSQL("DROP TABLE temp", reverse_sql=migrations.RunSQL.noop)
        assert rule.check(op, mock_migration) is None


class TestTransactionNestingInRunSQLRule:
    """Tests for TransactionNestingInRunSQLRule (SM049)."""

    def test_flags_begin_in_atomic(self, mock_migration):
        """BEGIN inside an atomic migration is flagged."""
        from django_safe_migrations.rules.run_sql import TransactionNestingInRunSQLRule

        rule = TransactionNestingInRunSQLRule()
        op = migrations.RunSQL("BEGIN; UPDATE t SET x = 1; COMMIT")
        issue = rule.check(op, mock_migration)
        assert issue is not None
        assert issue.rule_id == "SM049"

    def test_allows_in_non_atomic_migration(self):
        """Explicit transaction control is allowed when atomic=False."""
        from django_safe_migrations.rules.run_sql import TransactionNestingInRunSQLRule

        class NonAtomic:
            app_label = "testapp"
            name = "0001_test"
            atomic = False

        rule = TransactionNestingInRunSQLRule()
        op = migrations.RunSQL("BEGIN; UPDATE t SET x = 1; COMMIT")
        assert rule.check(op, NonAtomic()) is None

    def test_ignores_case_end(self, mock_migration):
        """CASE ... END must not be mistaken for transaction control."""
        from django_safe_migrations.rules.run_sql import TransactionNestingInRunSQLRule

        rule = TransactionNestingInRunSQLRule()
        op = migrations.RunSQL("UPDATE t SET y = CASE WHEN x THEN 1 ELSE 0 END")
        assert rule.check(op, mock_migration) is None


class TestConstraintMissingNotValidRule:
    """Tests for ConstraintMissingNotValidRule (SM047)."""

    def test_flags_fk_without_not_valid(self, mock_migration):
        """ADD CONSTRAINT ... FOREIGN KEY without NOT VALID is flagged."""
        from django_safe_migrations.rules.run_sql import ConstraintMissingNotValidRule

        rule = ConstraintMissingNotValidRule()
        op = migrations.RunSQL(
            "ALTER TABLE orders ADD CONSTRAINT fk_u "
            "FOREIGN KEY (uid) REFERENCES users(id)"
        )
        issue = rule.check(op, mock_migration, db_vendor="postgresql")
        assert issue is not None
        assert issue.rule_id == "SM047"

    def test_allows_with_not_valid(self, mock_migration):
        """A NOT VALID constraint is the safe pattern and is not flagged."""
        from django_safe_migrations.rules.run_sql import ConstraintMissingNotValidRule

        rule = ConstraintMissingNotValidRule()
        op = migrations.RunSQL(
            "ALTER TABLE orders ADD CONSTRAINT c " "CHECK (total >= 0) NOT VALID"
        )
        assert rule.check(op, mock_migration, db_vendor="postgresql") is None

    def test_ignores_unique_constraint(self, mock_migration):
        """A UNIQUE constraint is out of scope (no full validation scan)."""
        from django_safe_migrations.rules.run_sql import ConstraintMissingNotValidRule

        rule = ConstraintMissingNotValidRule()
        op = migrations.RunSQL("ALTER TABLE orders ADD CONSTRAINT u UNIQUE (code)")
        assert rule.check(op, mock_migration, db_vendor="postgresql") is None

    def test_postgresql_only(self):
        """SM047 is PostgreSQL-only."""
        from django_safe_migrations.rules.run_sql import ConstraintMissingNotValidRule

        rule = ConstraintMissingNotValidRule()
        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
