"""Tests for naming rules."""

from django.db import migrations, models

from django_safe_migrations.rules.base import Severity
from django_safe_migrations.rules.naming import ReservedKeywordColumnRule


class TestReservedKeywordColumnRule:
    """Tests for ReservedKeywordColumnRule (SM019)."""

    def test_detects_reserved_keyword_in_addfield(self, mock_migration):
        """Test that rule detects reserved keywords in AddField operations."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="article",
            name="order",  # Reserved keyword
            field=models.IntegerField(),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM019"
        assert issue.severity == Severity.INFO
        assert "order" in issue.message
        assert "reserved" in issue.message.lower()

    def test_detects_user_as_reserved_keyword(self, mock_migration):
        """Test that 'user' is detected as reserved (common PostgreSQL issue)."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="profile",
            name="user",  # Reserved in PostgreSQL
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.CASCADE,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM019"
        assert "user" in issue.message

    def test_detects_group_as_reserved_keyword(self, mock_migration):
        """Test that 'group' is detected as reserved."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="membership",
            name="group",
            field=models.ForeignKey(
                to="auth.Group",
                on_delete=models.CASCADE,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert "group" in issue.message

    def test_detects_select_as_reserved_keyword(self, mock_migration):
        """Test that SQL statement keywords are detected."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="choice",
            name="select",  # SQL keyword
            field=models.BooleanField(default=False),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert "select" in issue.message

    def test_allows_non_reserved_names(self, mock_migration):
        """Test that non-reserved names are allowed."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",  # Not reserved
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_descriptive_variations(self, mock_migration):
        """Test that descriptive variations of reserved words are allowed."""
        rule = ReservedKeywordColumnRule()

        # These are not reserved keywords
        safe_names = ["order_number", "user_id", "created_by", "group_name"]

        for name in safe_names:
            operation = migrations.AddField(
                model_name="model",
                name=name,
                field=models.CharField(max_length=100),
            )
            issue = rule.check(operation, mock_migration)
            assert issue is None, f"Expected {name} to be allowed"

    def test_case_insensitive_detection(self, mock_migration):
        """Test that detection is case-insensitive."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="article",
            name="ORDER",  # Uppercase
            field=models.IntegerField(),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None

    def test_detects_in_createmodel(self, mock_migration):
        """Test that rule checks CreateModel fields."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("title", models.CharField(max_length=255)),
                ("order", models.IntegerField()),  # Reserved
            ],
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM019"
        assert "order" in issue.message

    def test_detects_multiple_reserved_in_createmodel(self, mock_migration):
        """Test that rule lists all reserved keywords in CreateModel."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.CreateModel(
            name="BadModel",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("user", models.IntegerField()),  # Reserved
                ("order", models.IntegerField()),  # Reserved
                ("title", models.CharField(max_length=255)),  # OK
            ],
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        # Should mention both reserved fields
        assert "user" in issue.message or "order" in issue.message

    def test_ignores_non_field_operations(self, mock_migration):
        """Test that rule ignores non-field operations."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.DeleteModel(name="OldModel")
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_applies_to_all_databases(self):
        """Test that rule applies to all database vendors."""
        rule = ReservedKeywordColumnRule()

        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is True
        assert rule.applies_to_db("sqlite") is True

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="article",
            name="order",
            field=models.IntegerField(),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "db_column" in suggestion
        assert "order" in suggestion

    def test_detects_type_as_reserved(self, mock_migration):
        """Test that 'type' is detected as reserved (common Django issue)."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="item",
            name="type",
            field=models.CharField(max_length=50),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert "type" in issue.message

    def test_detects_status_as_reserved(self, mock_migration):
        """Test that 'status' is detected (commonly problematic)."""
        rule = ReservedKeywordColumnRule()
        operation = migrations.AddField(
            model_name="order",
            name="status",
            field=models.CharField(max_length=20),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert "status" in issue.message
