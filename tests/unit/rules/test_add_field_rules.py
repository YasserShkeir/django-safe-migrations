"""Tests for AddField rules."""

from django.db import migrations, models

from django_safe_migrations.rules.add_field import NotNullWithoutDefaultRule
from django_safe_migrations.rules.base import Severity


class TestNotNullWithoutDefaultRule:
    """Tests for NotNullWithoutDefaultRule (SM001)."""

    def test_detects_not_null_without_default(
        self, not_null_field_operation, mock_migration
    ):
        """Test that rule detects NOT NULL field without default."""
        rule = NotNullWithoutDefaultRule()
        issue = rule.check(not_null_field_operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM001"
        assert issue.severity == Severity.ERROR
        assert "email" in issue.message
        assert "NOT NULL" in issue.message

    def test_allows_nullable_field(self, nullable_field_operation, mock_migration):
        """Test that rule allows nullable fields."""
        rule = NotNullWithoutDefaultRule()
        issue = rule.check(nullable_field_operation, mock_migration)

        assert issue is None

    def test_allows_field_with_default(
        self, field_with_default_operation, mock_migration
    ):
        """Test that rule allows fields with default values."""
        rule = NotNullWithoutDefaultRule()
        issue = rule.check(field_with_default_operation, mock_migration)

        assert issue is None

    def test_allows_auto_field(self, mock_migration):
        """Test that rule allows auto fields (primary keys)."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_bigauto_field(self, mock_migration):
        """Test that rule allows BigAutoField."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.BigAutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.RemoveField(
            model_name="user",
            name="email",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, not_null_field_operation):
        """Test that rule provides a helpful suggestion."""
        rule = NotNullWithoutDefaultRule()
        suggestion = rule.get_suggestion(not_null_field_operation)

        assert suggestion is not None
        assert "nullable" in suggestion.lower()
        assert "backfill" in suggestion.lower()
        assert "NOT NULL" in suggestion

    def test_allows_boolean_with_default(self, mock_migration):
        """Test that BooleanField with default is allowed."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_boolean_without_default(self, mock_migration):
        """Test that BooleanField without default is detected."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(),  # No default, NOT NULL by default
        )
        result = rule.check(operation, mock_migration)

        # BooleanField has null=False and no default, so SM001 should flag it
        assert result is not None
        assert result.rule_id == "SM001"

    def test_allows_nullable_foreign_key(self, mock_migration):
        """Test that nullable ForeignKey is allowed."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                to="auth.User",
                on_delete=models.SET_NULL,
                null=True,
            ),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None


class TestExpensiveDefaultCallableRule:
    """Tests for ExpensiveDefaultCallableRule (SM022)."""

    def test_detects_timezone_now_default(self, mock_migration):
        """Test that rule detects timezone.now as default."""
        from django.utils import timezone

        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(default=timezone.now),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM022"
        assert issue.severity == Severity.WARNING
        assert "created_at" in issue.message

    def test_detects_datetime_now_default(self, mock_migration):
        """Test that rule detects datetime.now as default."""
        from datetime import datetime

        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(default=datetime.now),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM022"

    def test_allows_uuid4_default(self, mock_migration):
        """Test that rule allows uuid.uuid4 (fast)."""
        import uuid

        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4),
        )
        issue = rule.check(operation, mock_migration)

        # uuid4 is fast and should be allowed
        assert issue is None

    def test_allows_static_default(self, mock_migration):
        """Test that rule allows static default values."""
        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="status",
            field=models.CharField(max_length=50, default="draft"),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.RemoveField(
            model_name="user",
            name="email",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self, mock_migration):
        """Test that rule provides a helpful suggestion."""
        from django.utils import timezone

        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(default=timezone.now),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "auto_now_add" in suggestion.lower() or "batch" in suggestion.lower()

    def test_exact_match_does_not_flag_substring(self, mock_migration):
        """Test that SM022 uses exact match, not substring match.

        A callable named 'renow_something' should NOT be flagged just
        because it contains 'now' as a substring.
        """
        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        def renow_something():
            return "value"

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="field",
            field=models.CharField(max_length=50, default=renow_something),
        )
        issue = rule.check(operation, mock_migration)

        # Should NOT match because 'renow_something' is not an exact match
        # for any entry in SLOW_CALLABLES
        assert issue is None

    def test_exact_match_flags_known_slow_callable(self, mock_migration):
        """Test that SM022 still flags exact matches like 'now'."""
        from django.utils import timezone

        from django_safe_migrations.rules.add_field import ExpensiveDefaultCallableRule

        rule = ExpensiveDefaultCallableRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(default=timezone.now),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM022"


class TestNotNullWithoutDefaultRuleUUIDField:
    """Tests for SM001 UUIDField handling (v0.5.0 fix).

    UUIDField is no longer unconditionally whitelisted. It should only
    be allowed if it has a default (like uuid.uuid4).
    """

    def test_detects_uuidfield_without_default(self, mock_migration):
        """Test that UUIDField without default IS flagged by SM001."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(),  # No default, NOT NULL by default
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM001"

    def test_allows_uuidfield_with_uuid4_default(self, mock_migration):
        """Test that UUIDField with uuid4 default is allowed."""
        import uuid

        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_nullable_uuidfield(self, mock_migration):
        """Test that nullable UUIDField is allowed."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(null=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None


class TestNotNullWithoutDefaultRuleDbDefault:
    """Tests for SM001 db_default handling (v0.5.0 fix).

    Fields with db_default (Django 5.0+) should be treated as having
    a default value and not flagged.
    """

    def test_allows_field_with_db_default(self, mock_migration):
        """Test that a field with db_default is not flagged."""
        rule = NotNullWithoutDefaultRule()
        field = models.IntegerField()
        # Simulate Django 5.0+ db_default by setting the attribute
        field.db_default = 0  # A non-NOT_PROVIDED value
        operation = migrations.AddField(
            model_name="user",
            name="count",
            field=field,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_field_without_db_default(self, mock_migration):
        """Test that a field without db_default is still flagged."""
        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="count",
            field=models.IntegerField(),  # No default, no db_default
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM001"


class TestPreferBigIntRule:
    """Tests for PreferBigIntRule (SM028)."""

    def test_detects_autofield_pk(self, mock_migration):
        """Test that rule detects AutoField primary key."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM028"
        assert issue.severity == Severity.WARNING
        assert "id" in issue.message
        assert "AutoField" in issue.message
        assert "BigAutoField" in issue.message

    def test_detects_smallautofield_pk(self, mock_migration):
        """Test that rule detects SmallAutoField primary key."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="order",
            name="id",
            field=models.SmallAutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM028"
        assert "SmallAutoField" in issue.message

    def test_allows_bigautofield_pk(self, mock_migration):
        """Test that rule allows BigAutoField primary key."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.BigAutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_autofield_not_pk(self, mock_migration):
        """Test that rule ignores AutoField that is not a primary key."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="user",
            name="counter",
            field=models.AutoField(primary_key=False),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_autofield_in_create_model(self, mock_migration):
        """Test that rule detects AutoField pk in CreateModel."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("title", models.CharField(max_length=200)),
            ],
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM028"
        assert "id" in issue.message
        assert "Article" in issue.message

    def test_allows_bigautofield_in_create_model(self, mock_migration):
        """Test that rule allows BigAutoField in CreateModel."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("title", models.CharField(max_length=200)),
            ],
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_non_createmodel(self, mock_migration):
        """Test that rule ignores RemoveField and other operations."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.RemoveField(
            model_name="user",
            name="id",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_regular_field_addfield(self, mock_migration):
        """Test that rule ignores non-pk AddField operations."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_field import PreferBigIntRule

        rule = PreferBigIntRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "BigAutoField" in suggestion


class TestPreferTextOverVarcharRule:
    """Tests for PreferTextOverVarcharRule (SM031)."""

    def test_detects_charfield_with_large_max_length(self, mock_migration):
        """Test that rule detects CharField with max_length > 32."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM031"
        assert issue.severity == Severity.INFO
        assert "title" in issue.message
        assert "article" in issue.message
        assert "TextField" in issue.message

    def test_allows_charfield_with_small_max_length(self, mock_migration):
        """Test that rule allows CharField with max_length <= 32."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="status",
            field=models.CharField(max_length=20),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_charfield_with_max_length_32(self, mock_migration):
        """Test that rule allows CharField with max_length exactly 32."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="code",
            field=models.CharField(max_length=32),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_detects_charfield_with_max_length_33(self, mock_migration):
        """Test that rule detects CharField with max_length 33 (boundary)."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="slug",
            field=models.CharField(max_length=33),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM031"

    def test_ignores_textfield(self, mock_migration):
        """Test that rule ignores TextField (already the preferred type)."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="body",
            field=models.TextField(),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_integerfield(self, mock_migration):
        """Test that rule ignores non-CharField types."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="views",
            field=models.IntegerField(default=0),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.RemoveField(
            model_name="article",
            name="title",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_field import PreferTextOverVarcharRule

        rule = PreferTextOverVarcharRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",
            field=models.CharField(max_length=255),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "TextField" in suggestion


class TestPreferTimestampTZRule:
    """Tests for PreferTimestampTZRule (SM032)."""

    def test_detects_datetimefield_when_use_tz_false(self, mock_migration):
        """Test that rule detects DateTimeField when USE_TZ=False."""
        from django.test.utils import override_settings

        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(),
        )

        with override_settings(USE_TZ=False):
            issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM032"
        assert issue.severity == Severity.INFO
        assert "created_at" in issue.message
        assert "USE_TZ" in issue.message

    def test_allows_datetimefield_when_use_tz_true(self, mock_migration):
        """Test that rule allows DateTimeField when USE_TZ=True."""
        from django.test.utils import override_settings

        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(),
        )

        with override_settings(USE_TZ=True):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_datefield_when_use_tz_false(self, mock_migration):
        """Test that rule ignores DateField even when USE_TZ=False."""
        from django.test.utils import override_settings

        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.AddField(
            model_name="article",
            name="publish_date",
            field=models.DateField(),
        )

        with override_settings(USE_TZ=False):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.RemoveField(
            model_name="article",
            name="created_at",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_charfield_when_use_tz_false(self, mock_migration):
        """Test that rule ignores non-DateTimeField when USE_TZ=False."""
        from django.test.utils import override_settings

        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.AddField(
            model_name="article",
            name="title",
            field=models.CharField(max_length=255),
        )

        with override_settings(USE_TZ=False):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_field import PreferTimestampTZRule

        rule = PreferTimestampTZRule()
        operation = migrations.AddField(
            model_name="article",
            name="created_at",
            field=models.DateTimeField(),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "USE_TZ" in suggestion


class TestAddFieldWithDefaultRule:
    """Tests for AddFieldWithDefaultRule (SM033)."""

    def test_detects_not_null_field_with_default(self, mock_migration):
        """Test that rule detects NOT NULL field with a Python default."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="status",
            field=models.CharField(max_length=50, default="active"),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM033"
        assert issue.severity == Severity.WARNING
        assert "status" in issue.message
        assert "user" in issue.message

    def test_detects_integer_field_with_default(self, mock_migration):
        """Test that rule detects IntegerField with default."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="order",
            name="quantity",
            field=models.IntegerField(default=0),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM033"

    def test_detects_boolean_field_with_default(self, mock_migration):
        """Test that rule detects BooleanField with default."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM033"

    def test_allows_nullable_field_with_default(self, mock_migration):
        """Test that rule allows nullable field with default (no row rewrite)."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=100, null=True, default=""),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_field_without_default(self, mock_migration):
        """Test that rule allows NOT NULL field without default (SM001 handles)."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_autofield(self, mock_migration):
        """Test that rule allows AutoField."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_bigautofield(self, mock_migration):
        """Test that rule allows BigAutoField."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.BigAutoField(primary_key=True),
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_field_with_db_default(self, mock_migration):
        """Test that rule allows field with db_default (database-level default)."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        field = models.IntegerField(default=0)
        # Simulate db_default being set (Django 5.0+)
        field.db_default = 0
        operation = migrations.AddField(
            model_name="user",
            name="count",
            field=field,
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.RemoveField(
            model_name="user",
            name="status",
        )
        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_field import AddFieldWithDefaultRule

        rule = AddFieldWithDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="status",
            field=models.CharField(max_length=50, default="active"),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "nullable" in suggestion.lower() or "null" in suggestion.lower()
        assert "backfill" in suggestion.lower() or "batch" in suggestion.lower()


class TestPreferIdentityRule:
    """Tests for PreferIdentityRule (SM034)."""

    def test_detects_autofield_on_old_django(self, mock_migration):
        """Test that rule detects AutoField when Django < 4.0."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )

        with patch("django.VERSION", (3, 2, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM034"
        assert issue.severity == Severity.INFO
        assert "SERIAL" in issue.message
        assert "IDENTITY" in issue.message

    def test_detects_bigautofield_on_old_django(self, mock_migration):
        """Test that rule detects BigAutoField when Django < 4.0."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.BigAutoField(primary_key=True),
        )

        with patch("django.VERSION", (3, 2, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM034"
        assert "BigAutoField" in issue.message

    def test_allows_autofield_on_django_4_plus(self, mock_migration):
        """Test that rule allows AutoField when Django >= 4.0."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )

        with patch("django.VERSION", (4, 0, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_allows_autofield_on_django_5(self, mock_migration):
        """Test that rule allows AutoField when Django >= 5.0."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )

        with patch("django.VERSION", (5, 0, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_auto_fields_on_old_django(self, mock_migration):
        """Test that rule ignores non-auto fields even on old Django."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )

        with patch("django.VERSION", (3, 2, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_non_addfield_operations(self, mock_migration):
        """Test that rule ignores non-AddField operations."""
        from unittest.mock import patch

        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.RemoveField(
            model_name="user",
            name="id",
        )

        with patch("django.VERSION", (3, 2, 0, "final", 0)):
            issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_only_applies_to_postgresql(self):
        """Test that rule only applies to PostgreSQL."""
        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        assert rule.applies_to_db("postgresql") is True
        assert rule.applies_to_db("mysql") is False
        assert rule.applies_to_db("sqlite") is False

    def test_provides_suggestion(self):
        """Test that rule provides a helpful suggestion."""
        from django_safe_migrations.rules.add_field import PreferIdentityRule

        rule = PreferIdentityRule()
        operation = migrations.AddField(
            model_name="user",
            name="id",
            field=models.AutoField(primary_key=True),
        )
        suggestion = rule.get_suggestion(operation)

        assert suggestion is not None
        assert "IDENTITY" in suggestion
        assert "Django 4.0" in suggestion
