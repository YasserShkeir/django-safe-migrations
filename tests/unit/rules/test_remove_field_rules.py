"""Tests for RemoveField and DeleteModel rules."""

from django_safe_migrations.rules.base import Severity
from django_safe_migrations.rules.remove_field import (
    DropColumnUnsafeRule,
    DropTableUnsafeRule,
)


class TestDropColumnUnsafeRule:
    """Tests for DropColumnUnsafeRule (SM002)."""

    def test_detects_remove_field(self, remove_field_operation, mock_migration):
        """Test that rule detects RemoveField operations."""
        rule = DropColumnUnsafeRule()
        issue = rule.check(remove_field_operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM002"
        assert issue.severity == Severity.WARNING
        assert "old_field" in issue.message
        assert "user" in issue.message.lower()

    def test_ignores_non_removefield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RemoveField operations."""
        rule = DropColumnUnsafeRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, remove_field_operation):
        """Test that rule provides a helpful suggestion."""
        rule = DropColumnUnsafeRule()
        suggestion = rule.get_suggestion(remove_field_operation)

        assert suggestion is not None
        assert "expand" in suggestion.lower() or "contract" in suggestion.lower()
        assert "release" in suggestion.lower()


class TestDropTableUnsafeRule:
    """Tests for DropTableUnsafeRule (SM003)."""

    def test_detects_delete_model(self, delete_model_operation, mock_migration):
        """Test that rule detects DeleteModel operations."""
        rule = DropTableUnsafeRule()
        issue = rule.check(delete_model_operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM003"
        assert issue.severity == Severity.WARNING
        assert "OldModel" in issue.message

    def test_ignores_non_deletemodel_operations(
        self, remove_field_operation, mock_migration
    ):
        """Test that rule ignores non-DeleteModel operations."""
        rule = DropTableUnsafeRule()
        issue = rule.check(remove_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, delete_model_operation):
        """Test that rule provides a helpful suggestion."""
        rule = DropTableUnsafeRule()
        suggestion = rule.get_suggestion(delete_model_operation)

        assert suggestion is not None
        assert "release" in suggestion.lower()
        assert "foreign" in suggestion.lower() or "fk" in suggestion.lower()
