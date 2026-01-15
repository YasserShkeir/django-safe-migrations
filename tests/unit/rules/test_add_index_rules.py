"""Tests for AddIndex rules."""

from django.db import migrations, models

from django_safe_migrations.rules.add_index import (
    UnsafeIndexCreationRule,
    UnsafeUniqueConstraintRule,
)
from django_safe_migrations.rules.base import Severity


class TestUnsafeIndexCreationRule:
    """Tests for UnsafeIndexCreationRule (SM010)."""

    def test_detects_add_index(self, add_index_operation, mock_migration):
        """Test that rule detects AddIndex operations."""
        rule = UnsafeIndexCreationRule()
        issue = rule.check(add_index_operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM010"
        assert issue.severity == Severity.ERROR
        assert "user_email_idx" in issue.message

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        rule = UnsafeIndexCreationRule()

        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_ignores_non_addindex_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-AddIndex operations."""
        rule = UnsafeIndexCreationRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, add_index_operation):
        """Test that rule provides a helpful suggestion."""
        rule = UnsafeIndexCreationRule()
        suggestion = rule.get_suggestion(add_index_operation)

        assert suggestion is not None
        assert "concurrent" in suggestion.lower()
        assert "atomic = False" in suggestion


class TestUnsafeUniqueConstraintRule:
    """Tests for UnsafeUniqueConstraintRule (SM011)."""

    def test_detects_unique_constraint(
        self, add_unique_constraint_operation, mock_migration
    ):
        """Test that rule detects UniqueConstraint additions."""
        rule = UnsafeUniqueConstraintRule()
        issue = rule.check(add_unique_constraint_operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM011"
        assert issue.severity == Severity.ERROR
        assert "unique_user_email" in issue.message

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        rule = UnsafeUniqueConstraintRule()

        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_ignores_non_unique_constraints(self, mock_migration):
        """Test that rule ignores non-unique constraints."""
        rule = UnsafeUniqueConstraintRule()

        # CheckConstraint should not trigger this rule
        # Django 5+ uses 'condition', older versions use 'check'
        try:
            operation = migrations.AddConstraint(
                model_name="user",
                constraint=models.CheckConstraint(
                    condition=models.Q(age__gte=0),
                    name="age_positive",
                ),
            )
        except TypeError:
            # Fallback for older Django versions
            operation = migrations.AddConstraint(
                model_name="user",
                constraint=models.CheckConstraint(
                    check=models.Q(age__gte=0),
                    name="age_positive",
                ),
            )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addconstraint_operations(
        self, add_index_operation, mock_migration
    ):
        """Test that rule ignores non-AddConstraint operations."""
        rule = UnsafeUniqueConstraintRule()
        issue = rule.check(add_index_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, add_unique_constraint_operation):
        """Test that rule provides a helpful suggestion."""
        rule = UnsafeUniqueConstraintRule()
        suggestion = rule.get_suggestion(add_unique_constraint_operation)

        assert suggestion is not None
        assert "concurrent" in suggestion.lower()
        assert "USING INDEX" in suggestion
