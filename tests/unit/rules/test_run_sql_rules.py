"""Tests for RunSQL and RunPython rules."""

from django.db import migrations

from django_safe_migrations.rules.base import Severity
from django_safe_migrations.rules.run_sql import (
    EnumAddValueInTransactionRule,
    LargeDataMigrationRule,
    RunPythonWithoutReverseRule,
    RunSQLWithoutReverseRule,
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
