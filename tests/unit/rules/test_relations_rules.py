"""Tests for relation rules (ManyToMany, ForeignKey)."""

from django.db import migrations, models

from django_safe_migrations.rules.base import Severity
from django_safe_migrations.rules.relations import (
    AddManyToManyRule,
    ForeignKeyWithoutIndexRule,
)


class TestAddManyToManyRule:
    """Tests for AddManyToManyRule (SM023)."""

    def test_detects_manytomany_field(self, mock_migration):
        """Test that rule detects ManyToManyField addition."""
        rule = AddManyToManyRule()
        operation = migrations.AddField(
            model_name="article",
            name="tags",
            field=models.ManyToManyField(to="tags.Tag"),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM023"
        assert issue.severity == Severity.INFO
        assert "tags" in issue.message
        assert "junction" in issue.message.lower() or "table" in issue.message.lower()

    def test_ignores_non_manytomany_fields(self, mock_migration):
        """Test that rule ignores non-ManyToMany fields."""
        rule = AddManyToManyRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_regular_charfield(self, mock_migration):
        """Test that rule ignores regular fields."""
        rule = AddManyToManyRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        rule = AddManyToManyRule()
        operation = migrations.RemoveField(
            model_name="article",
            name="tags",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = AddManyToManyRule()
        operation = migrations.AddField(
            model_name="article",
            name="tags",
            field=models.ManyToManyField(to="tags.Tag"),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        # Should mention that it creates a junction table
        assert "table" in suggestion.lower()


class TestForeignKeyWithoutIndexRule:
    """Tests for ForeignKeyWithoutIndexRule (SM025)."""

    def test_detects_fk_with_db_index_false(self, mock_migration):
        """Test that rule detects ForeignKey with db_index=False."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
                db_index=False,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM025"
        assert issue.severity == Severity.WARNING
        assert "author" in issue.message
        assert "index" in issue.message.lower()

    def test_allows_fk_with_default_index(self, mock_migration):
        """Test that rule allows ForeignKey with default indexing."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
            ),
        )
        issue = rule.check(operation, mock_migration)

        # By default, Django creates an index for FK
        assert issue is None

    def test_allows_fk_with_explicit_db_index_true(self, mock_migration):
        """Test that rule allows ForeignKey with explicit db_index=True."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
                db_index=True,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_onetoone_with_db_index_false(self, mock_migration):
        """Test that rule detects OneToOneField with db_index=False."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="profile",
            name="user",
            field=models.OneToOneField(
                to="auth.User",
                on_delete=models.CASCADE,
                db_index=False,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM025"

    def test_ignores_non_fk_fields(self, mock_migration):
        """Test that rule ignores non-ForeignKey fields."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.RemoveField(
            model_name="article",
            name="author",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = ForeignKeyWithoutIndexRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
                db_index=False,
            ),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "index" in suggestion.lower()
        assert "join" in suggestion.lower() or "performance" in suggestion.lower()
