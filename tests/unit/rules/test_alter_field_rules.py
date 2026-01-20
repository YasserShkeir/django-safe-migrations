"""Tests for AlterField rules."""

from django.db import migrations, models

from django_safe_migrations.rules.alter_field import (
    AddForeignKeyValidatesRule,
    AlterColumnTypeRule,
    AlterVarcharLengthRule,
    RenameColumnRule,
    RenameModelRule,
)
from django_safe_migrations.rules.base import Severity


class TestAlterColumnTypeRule:
    """Tests for AlterColumnTypeRule (SM004)."""

    def test_detects_alter_field(self, mock_migration):
        """Test that rule detects AlterField operations."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="status",
            field=models.IntegerField(),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM004"
        assert issue.severity == Severity.WARNING
        assert "status" in issue.message
        assert "user" in issue.message.lower()

    def test_ignores_non_alterfield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-AlterField operations."""
        rule = AlterColumnTypeRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "expand" in suggestion.lower() or "contract" in suggestion.lower()

    # Smarter detection tests (v0.3.0)

    def test_skips_alterfield_adding_null_true(self, mock_migration):
        """Test that rule skips AlterField when adding null=True (safe)."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, null=True),
        )
        issue = rule.check(operation, mock_migration)

        # Adding null=True is safe (removes NOT NULL constraint)
        assert issue is None

    def test_skips_alterfield_on_textfield(self, mock_migration):
        """Test that rule skips AlterField on TextField (usually metadata only)."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="bio",
            field=models.TextField(),
        )
        issue = rule.check(operation, mock_migration)

        # TextField alterations are usually metadata-only
        assert issue is None

    def test_skips_alterfield_on_booleanfield(self, mock_migration):
        """Test that rule skips AlterField on BooleanField (safe)."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        )
        issue = rule.check(operation, mock_migration)

        # BooleanField alterations are typically safe
        assert issue is None

    def test_detects_charfield_without_null_true(self, mock_migration):
        """Test that rule still detects CharField without null=True."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=100),
        )
        issue = rule.check(operation, mock_migration)

        # CharField without null=True could be type change, so flag it
        assert issue is not None
        assert issue.rule_id == "SM004"

    def test_detects_integerfield_alteration(self, mock_migration):
        """Test that rule detects IntegerField alteration (potentially unsafe)."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="order",
            name="quantity",
            field=models.IntegerField(),
        )
        issue = rule.check(operation, mock_migration)

        # IntegerField changes could involve type changes
        assert issue is not None
        assert issue.rule_id == "SM004"

    def test_skips_integerfield_with_null_true(self, mock_migration):
        """Test that rule skips IntegerField with null=True."""
        rule = AlterColumnTypeRule()
        operation = migrations.AlterField(
            model_name="order",
            name="quantity",
            field=models.IntegerField(null=True),
        )
        issue = rule.check(operation, mock_migration)

        # Adding null=True is safe even for IntegerField
        assert issue is None


class TestAddForeignKeyValidatesRule:
    """Tests for AddForeignKeyValidatesRule (SM005)."""

    def test_detects_foreign_key_with_constraint(self, mock_migration):
        """Test that rule detects ForeignKey with db_constraint=True."""
        rule = AddForeignKeyValidatesRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM005"
        assert issue.severity == Severity.WARNING
        assert "author" in issue.message

    def test_allows_foreign_key_without_constraint(self, mock_migration):
        """Test that rule allows ForeignKey with db_constraint=False."""
        rule = AddForeignKeyValidatesRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
                db_constraint=False,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_foreign_key_fields(self, mock_migration):
        """Test that rule ignores non-FK fields."""
        rule = AddForeignKeyValidatesRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = AddForeignKeyValidatesRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
            ),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "db_constraint=False" in suggestion


class TestRenameColumnRule:
    """Tests for RenameColumnRule (SM006)."""

    def test_detects_rename_field(self, mock_migration):
        """Test that rule detects RenameField operations."""
        rule = RenameColumnRule()
        operation = migrations.RenameField(
            model_name="user",
            old_name="username",
            new_name="login",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM006"
        assert issue.severity == Severity.INFO
        assert "username" in issue.message
        assert "login" in issue.message

    def test_ignores_non_renamefield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RenameField operations."""
        rule = RenameColumnRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = RenameColumnRule()
        operation = migrations.RenameField(
            model_name="user",
            old_name="username",
            new_name="login",
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "zero-downtime" in suggestion.lower()


class TestAlterVarcharLengthRule:
    """Tests for AlterVarcharLengthRule (SM013)."""

    def test_detects_charfield_alter(self, mock_migration):
        """Test that rule detects AlterField on CharField."""
        rule = AlterVarcharLengthRule()
        operation = migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=50),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM013"
        assert issue.severity == Severity.WARNING
        assert "username" in issue.message

    def test_ignores_non_charfield(self, mock_migration):
        """Test that rule ignores non-CharField types."""
        rule = AlterVarcharLengthRule()
        operation = migrations.AlterField(
            model_name="user",
            name="bio",
            field=models.TextField(),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_addfield(self, mock_migration):
        """Test that rule ignores AddField operations."""
        rule = AlterVarcharLengthRule()
        operation = migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=100),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = AlterVarcharLengthRule()
        operation = migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=50),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "VARCHAR" in suggestion or "max_length" in suggestion


class TestRenameModelRule:
    """Tests for RenameModelRule (SM014)."""

    def test_detects_rename_model(self, mock_migration):
        """Test that rule detects RenameModel operations."""
        rule = RenameModelRule()
        operation = migrations.RenameModel(
            old_name="OldUser",
            new_name="NewUser",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM014"
        assert issue.severity == Severity.WARNING
        assert "OldUser" in issue.message
        assert "NewUser" in issue.message
        assert "foreign key" in issue.message.lower()

    def test_ignores_non_renamemodel_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-RenameModel operations."""
        rule = RenameModelRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_ignores_rename_field(self, mock_migration):
        """Test that rule ignores RenameField operations."""
        rule = RenameModelRule()
        operation = migrations.RenameField(
            model_name="user",
            old_name="username",
            new_name="login",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = RenameModelRule()
        operation = migrations.RenameModel(
            old_name="OldModel",
            new_name="NewModel",
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "db_table" in suggestion
        assert (
            "foreign key" in suggestion.lower() or "foreign keys" in suggestion.lower()
        )
