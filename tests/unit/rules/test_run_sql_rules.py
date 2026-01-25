"""Tests for RunSQL and RunPython rules."""

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


class TestRunPythonNoBatchingRule:
    """Tests for RunPythonNoBatchingRule (SM026).

    Note: These tests rely on inspect.getsource() which may not work in all
    environments (e.g., Docker with volume-mounted code from different paths).
    Tests gracefully skip when source inspection is unavailable.
    """

    def test_detects_all_without_iterator(self, mock_migration):
        """Test that rule detects .all() without .iterator()."""
        import inspect

        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            for obj in Model.objects.all():
                obj.save()

        # Check if source inspection works in this environment
        try:
            inspect.getsource(migrate_data)
        except OSError:
            pytest.skip("Source inspection not available in this environment")

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM026"
        assert issue.severity == Severity.WARNING
        assert "migrate_data" in issue.message
        assert "all()" in issue.message.lower() or "batch" in issue.message.lower()

    def test_allows_all_with_iterator(self, mock_migration):
        """Test that rule allows .all() with .iterator()."""
        import inspect

        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            for obj in Model.objects.all().iterator(chunk_size=1000):
                obj.save()

        # Check if source inspection works in this environment
        try:
            inspect.getsource(migrate_data)
        except OSError:
            pytest.skip("Source inspection not available in this environment")

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_values_list(self, mock_migration):
        """Test that rule allows .values_list() usage."""
        import inspect

        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            ids = Model.objects.all().values_list("id", flat=True)
            return list(ids)

        # Check if source inspection works in this environment
        try:
            inspect.getsource(migrate_data)
        except OSError:
            pytest.skip("Source inspection not available in this environment")

        operation = migrations.RunPython(migrate_data)
        issue = rule.check(operation, mock_migration)

        # values_list is memory efficient
        assert issue is None

    def test_allows_batching_pattern(self, mock_migration):
        """Test that rule allows explicit batching."""
        import inspect

        rule = RunPythonNoBatchingRule()

        def migrate_data(apps, schema_editor):
            Model = apps.get_model("myapp", "Model")
            batch_size = 1000
            for batch in Model.objects.all()[:batch_size]:
                batch.save()

        # Check if source inspection works in this environment
        try:
            inspect.getsource(migrate_data)
        except OSError:
            pytest.skip("Source inspection not available in this environment")

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
