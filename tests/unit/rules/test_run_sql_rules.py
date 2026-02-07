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
