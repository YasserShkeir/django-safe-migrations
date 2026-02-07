"""Tests for AddIndex rules."""

from unittest.mock import MagicMock

from django.db import migrations, models

from django_safe_migrations.rules.add_index import (
    ConcurrentInAtomicMigrationRule,
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


class TestConcurrentInAtomicMigrationRule:
    """Tests for ConcurrentInAtomicMigrationRule (SM018)."""

    def _create_mock_concurrent_operation(self, op_class_name: str):
        """Create a mock concurrent operation."""
        mock_op = MagicMock()
        mock_op.__class__.__name__ = op_class_name
        mock_op.model_name = "user"
        return mock_op

    def test_detects_add_index_concurrently_in_atomic_migration(self, mock_migration):
        """Test that rule detects AddIndexConcurrently in atomic migration."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = self._create_mock_concurrent_operation("AddIndexConcurrently")

        # Default migration is atomic (atomic=True implied)
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM018"
        assert issue.severity == Severity.ERROR
        assert "atomic = False" in issue.message
        assert "AddIndexConcurrently" in issue.message

    def test_detects_remove_index_concurrently_in_atomic_migration(
        self, mock_migration
    ):
        """Test that rule detects RemoveIndexConcurrently in atomic migration."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = self._create_mock_concurrent_operation("RemoveIndexConcurrently")

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM018"
        assert "RemoveIndexConcurrently" in issue.message

    def test_allows_concurrent_in_non_atomic_migration(self):
        """Test that rule allows concurrent operations when atomic=False."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = self._create_mock_concurrent_operation("AddIndexConcurrently")

        # Create migration with atomic = False
        mock_migration = MagicMock()
        mock_migration.atomic = False
        mock_migration.__module__ = "testapp.migrations.0001_initial"

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_concurrent_operations(self, mock_migration):
        """Test that rule ignores regular AddIndex operations."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_other_operations(self, not_null_field_operation, mock_migration):
        """Test that rule ignores non-index operations."""
        rule = ConcurrentInAtomicMigrationRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        rule = ConcurrentInAtomicMigrationRule()

        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = self._create_mock_concurrent_operation("AddIndexConcurrently")

        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "atomic = False" in suggestion
        assert "AddIndexConcurrently" in suggestion

    def test_explicit_atomic_true_still_flagged(self):
        """Test that explicit atomic=True is still flagged."""
        rule = ConcurrentInAtomicMigrationRule()
        operation = self._create_mock_concurrent_operation("AddIndexConcurrently")

        mock_migration = MagicMock()
        mock_migration.atomic = True  # Explicitly True
        mock_migration.__module__ = "testapp.migrations.0001_initial"

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM018"


class TestUnsafeIndexDeletionRule:
    """Tests for UnsafeIndexDeletionRule (SM030)."""

    def test_detects_remove_index(self, mock_migration):
        """Test that rule detects RemoveIndex operations."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        operation = migrations.RemoveIndex(
            model_name="user",
            name="user_email_idx",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM030"
        assert issue.severity == Severity.ERROR
        assert "user_email_idx" in issue.message
        assert "CONCURRENTLY" in issue.message

    def test_allows_remove_index_concurrently(self, mock_migration):
        """Test that rule allows RemoveIndexConcurrently."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()

        # Create a real subclass that mimics RemoveIndexConcurrently
        class RemoveIndexConcurrently(migrations.RemoveIndex):
            """Fake RemoveIndexConcurrently for testing."""

            pass

        operation = RemoveIndexConcurrently(
            model_name="user",
            name="user_email_idx",
        )
        issue = rule.check(operation, mock_migration)

        # RemoveIndexConcurrently should be allowed
        assert issue is None

    def test_ignores_non_removeindex_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RemoveIndex operations."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_ignores_add_index_operations(self, add_index_operation, mock_migration):
        """Test that rule ignores AddIndex operations."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        issue = rule.check(add_index_operation, mock_migration)

        assert issue is None

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        operation = migrations.RemoveIndex(
            model_name="user",
            name="user_email_idx",
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "RemoveIndexConcurrently" in suggestion
        assert "atomic = False" in suggestion or "atomic=False" in suggestion

    def test_includes_index_name_in_message(self, mock_migration):
        """Test that the issue message includes the index name."""
        from django_safe_migrations.rules.add_index import UnsafeIndexDeletionRule

        rule = UnsafeIndexDeletionRule()
        operation = migrations.RemoveIndex(
            model_name="order",
            name="order_created_at_idx",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert "order_created_at_idx" in issue.message
        assert "order" in issue.message
