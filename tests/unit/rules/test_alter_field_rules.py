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


class TestAlterColumnTypeRuleWithOldField:
    """Tests for SM004 with old_field comparison (before-state gap fix)."""

    def test_safe_when_only_null_changed(self, mock_migration):
        """Test safe change: same type, adding null=True."""
        rule = AlterColumnTypeRule()
        old_field = models.CharField(max_length=255)
        new_field = models.CharField(max_length=255, null=True)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_safe_when_only_default_changed(self, mock_migration):
        """Test safe change: same type, only default changed."""
        rule = AlterColumnTypeRule()
        old_field = models.CharField(max_length=100)
        new_field = models.CharField(max_length=100, default="new")
        operation = migrations.AlterField(
            model_name="user", name="status", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_safe_when_only_metadata_changed(self, mock_migration):
        """Test safe change: same type, only help_text changed."""
        rule = AlterColumnTypeRule()
        old_field = models.CharField(max_length=100, help_text="old")
        new_field = models.CharField(max_length=100, help_text="new")
        operation = migrations.AlterField(
            model_name="user", name="name", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_unsafe_when_type_changed(self, mock_migration):
        """Test unsafe change: type changed from CharField to IntegerField."""
        rule = AlterColumnTypeRule()
        old_field = models.CharField(max_length=100)
        new_field = models.IntegerField()
        operation = migrations.AlterField(
            model_name="user", name="code", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM004"

    def test_unsafe_when_max_length_decreased(self, mock_migration):
        """Test unsafe: same type but max_length decreased."""
        rule = AlterColumnTypeRule()
        old_field = models.CharField(max_length=255)
        new_field = models.CharField(max_length=50)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM004"


class TestAlterVarcharLengthRuleWithOldField:
    """Tests for SM013 with old_field comparison."""

    def test_safe_when_max_length_increased(self, mock_migration):
        """Test safe: increasing max_length."""
        rule = AlterVarcharLengthRule()
        old_field = models.CharField(max_length=50)
        new_field = models.CharField(max_length=255)
        operation = migrations.AlterField(
            model_name="user", name="name", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_unsafe_when_max_length_decreased(self, mock_migration):
        """Test unsafe: decreasing max_length."""
        rule = AlterVarcharLengthRule()
        old_field = models.CharField(max_length=255)
        new_field = models.CharField(max_length=50)
        operation = migrations.AlterField(
            model_name="user", name="name", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM013"
        assert "255" in issue.message
        assert "50" in issue.message

    def test_safe_when_max_length_unchanged(self, mock_migration):
        """Test safe: max_length unchanged."""
        rule = AlterVarcharLengthRule()
        old_field = models.CharField(max_length=100)
        new_field = models.CharField(max_length=100)
        operation = migrations.AlterField(
            model_name="user", name="name", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_skips_when_old_field_is_not_charfield(self, mock_migration):
        """Test skips when old field was a different type."""
        rule = AlterVarcharLengthRule()
        old_field = models.IntegerField()
        new_field = models.CharField(max_length=50)
        operation = migrations.AlterField(
            model_name="user", name="code", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None


class TestAlterFieldNullFalseRuleWithOldField:
    """Tests for SM020 with old_field comparison."""

    def test_warns_when_changing_nullable_to_not_null(self, mock_migration):
        """Test warns when field was nullable and now is NOT NULL."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        old_field = models.CharField(max_length=255, null=True)
        new_field = models.CharField(max_length=255, null=False)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM020"

    def test_skips_when_field_was_already_not_null(self, mock_migration):
        """Test skips when field was already NOT NULL."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        old_field = models.CharField(max_length=255)  # null=False by default
        new_field = models.CharField(max_length=255, default="x")  # still NOT NULL
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None


class TestAlterFieldUniqueRuleWithOldField:
    """Tests for SM021 with old_field comparison."""

    def test_warns_when_adding_unique(self, mock_migration):
        """Test warns when unique=True is being added."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        old_field = models.CharField(max_length=255)
        new_field = models.CharField(max_length=255, unique=True)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(
            operation, mock_migration, old_field=old_field, db_vendor="postgresql"
        )

        assert issue is not None
        assert issue.rule_id == "SM021"

    def test_skips_when_already_unique(self, mock_migration):
        """Test skips when field was already unique."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        old_field = models.CharField(max_length=255, unique=True)
        new_field = models.CharField(max_length=255, unique=True)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(
            operation, mock_migration, old_field=old_field, db_vendor="postgresql"
        )

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


class TestAlterFieldNullFalseRule:
    """Tests for AlterFieldNullFalseRule (SM020)."""

    def test_detects_alterfield_null_false(self, mock_migration):
        """Test that rule detects AlterField with null=False."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, null=False),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM020"
        assert issue.severity == Severity.ERROR
        assert "email" in issue.message
        assert (
            "null=false" in issue.message.lower() or "not null" in issue.message.lower()
        )

    def test_detects_alterfield_implicit_null_false(self, mock_migration):
        """Test that rule detects AlterField with implicit null=False (default)."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        # CharField without null=True defaults to null=False
        operation = migrations.AlterField(
            model_name="user",
            name="status",
            field=models.CharField(max_length=50),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM020"

    def test_allows_alterfield_null_true(self, mock_migration):
        """Test that rule allows AlterField with null=True."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        operation = migrations.AlterField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=255, null=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_alterfield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-AlterField operations."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.alter_field import AlterFieldNullFalseRule

        rule = AlterFieldNullFalseRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "backfill" in suggestion.lower() or "default" in suggestion.lower()


class TestAlterFieldUniqueRule:
    """Tests for AlterFieldUniqueRule (SM021)."""

    def test_detects_alterfield_unique_true(self, mock_migration):
        """Test that rule detects AlterField with unique=True."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, unique=True),
        )
        issue = rule.check(operation, mock_migration, db_vendor="postgresql")

        assert issue is not None
        assert issue.rule_id == "SM021"
        assert issue.severity == Severity.ERROR
        assert "email" in issue.message
        assert "unique" in issue.message.lower()

    def test_allows_alterfield_without_unique(self, mock_migration):
        """Test that rule allows AlterField without unique=True."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration, db_vendor="postgresql")

        assert issue is None

    def test_ignores_non_alterfield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-AlterField operations."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_applies_to_postgresql(self):
        """Test that rule applies to PostgreSQL."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        assert rule.applies_to_db("postgresql")

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.alter_field import AlterFieldUniqueRule

        rule = AlterFieldUniqueRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, unique=True),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "concurrent" in suggestion.lower() or "index" in suggestion.lower()


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


class TestDropNotNullRule:
    """Tests for DropNotNullRule (SM029)."""

    def test_detects_dropping_not_null_with_old_field(self, mock_migration):
        """Test that rule detects change from NOT NULL to nullable."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        old_field = models.CharField(max_length=255)  # null=False by default
        new_field = models.CharField(max_length=255, null=True)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM029"
        assert issue.severity == Severity.WARNING
        assert "email" in issue.message
        assert "user" in issue.message
        assert "NULL" in issue.message

    def test_skips_when_field_was_already_nullable(self, mock_migration):
        """Test that rule skips when field was already nullable."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        old_field = models.CharField(max_length=255, null=True)
        new_field = models.CharField(max_length=255, null=True)
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_skips_when_new_field_is_not_null(self, mock_migration):
        """Test that rule skips when new field is NOT NULL (not dropping)."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        old_field = models.CharField(max_length=255)  # null=False
        new_field = models.CharField(max_length=255)  # null=False
        operation = migrations.AlterField(
            model_name="user", name="email", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is None

    def test_returns_none_without_old_field(self, mock_migration):
        """Test that rule returns None when old_field is not available."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, null=True),
        )
        # No old_field provided
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_alterfield_operations(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule ignores non-AlterField operations."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is None

    def test_detects_integerfield_drop_not_null(self, mock_migration):
        """Test that rule detects dropping NOT NULL on IntegerField."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        old_field = models.IntegerField()  # null=False by default
        new_field = models.IntegerField(null=True)
        operation = migrations.AlterField(
            model_name="order", name="quantity", field=new_field
        )
        issue = rule.check(operation, mock_migration, old_field=old_field)

        assert issue is not None
        assert issue.rule_id == "SM029"
        assert "quantity" in issue.message

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.alter_field import DropNotNullRule

        rule = DropNotNullRule()
        operation = migrations.AlterField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, null=True),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "NULL" in suggestion or "null" in suggestion.lower()
        assert "email" in suggestion
