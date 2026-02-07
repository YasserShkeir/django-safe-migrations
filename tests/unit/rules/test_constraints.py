"""Tests for constraint rules (SM009, SM015, SM017)."""

from __future__ import annotations

from unittest.mock import MagicMock

import django
import pytest
from django.db import migrations, models

from django_safe_migrations.rules.constraints import (
    AddCheckConstraintRule,
    AddUniqueConstraintRule,
    AlterUniqueTogetherRule,
)


def get_check_constraint(**kwargs):
    """Create a CheckConstraint compatible with Django version."""
    if django.VERSION >= (5, 1):
        if "check" in kwargs:
            kwargs["condition"] = kwargs.pop("check")
    return models.CheckConstraint(**kwargs)


class TestAddUniqueConstraintRule:
    """Tests for SM009: AddUniqueConstraint rule."""

    @pytest.fixture
    def rule(self) -> AddUniqueConstraintRule:
        """Create rule instance."""
        return AddUniqueConstraintRule()

    @pytest.fixture
    def mock_migration(self) -> MagicMock:
        """Create a mock migration."""
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        return migration

    def test_detects_unique_constraint(
        self, rule: AddUniqueConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that adding a unique constraint is detected."""
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email", "tenant_id"],
                name="unique_email_per_tenant",
            ),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM009"
        assert "unique_email_per_tenant" in issue.message
        assert "email, tenant_id" in issue.message

    def test_ignores_check_constraint(
        self, rule: AddUniqueConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that check constraints are ignored."""
        operation = migrations.AddConstraint(
            model_name="order",
            constraint=get_check_constraint(
                check=models.Q(amount__gte=0),
                name="positive_amount",
            ),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_other_operations(
        self, rule: AddUniqueConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that other operations are ignored."""
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_get_suggestion(self, rule: AddUniqueConstraintRule) -> None:
        """Test that suggestion is returned."""
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
            ),
        )

        suggestion = rule.get_suggestion(operation)

        assert "AddIndexConcurrently" in suggestion
        assert "atomic = False" in suggestion


class TestAddUniqueConstraintRuleDeduplication:
    """Tests for SM009 deduplication with SM011 on PostgreSQL."""

    def test_skips_on_postgresql(self) -> None:
        """Test that SM009 defers to SM011 on PostgreSQL."""
        rule = AddUniqueConstraintRule()
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
            ),
        )

        issue = rule.check(operation, migration, db_vendor="postgresql")

        assert issue is None

    def test_fires_on_mysql(self) -> None:
        """Test that SM009 still fires on MySQL."""
        rule = AddUniqueConstraintRule()
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
            ),
        )

        issue = rule.check(operation, migration, db_vendor="mysql")

        assert issue is not None
        assert issue.rule_id == "SM009"

    def test_fires_when_no_db_vendor(self) -> None:
        """Test that SM009 fires when db_vendor is not specified."""
        rule = AddUniqueConstraintRule()
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
            ),
        )

        issue = rule.check(operation, migration)

        assert issue is not None
        assert issue.rule_id == "SM009"


class TestAlterUniqueTogetherRule:
    """Tests for SM015: AlterUniqueTogether rule."""

    @pytest.fixture
    def rule(self) -> AlterUniqueTogetherRule:
        """Create rule instance."""
        return AlterUniqueTogetherRule()

    @pytest.fixture
    def mock_migration(self) -> MagicMock:
        """Create a mock migration."""
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        return migration

    def test_detects_alter_unique_together(
        self, rule: AlterUniqueTogetherRule, mock_migration: MagicMock
    ) -> None:
        """Test that AlterUniqueTogether is detected."""
        operation = migrations.AlterUniqueTogether(
            name="user",
            unique_together={("email", "tenant_id")},
        )

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM015"
        assert "deprecated" in issue.message.lower()
        assert "UniqueConstraint" in issue.message

    def test_ignores_removing_unique_together(
        self, rule: AlterUniqueTogetherRule, mock_migration: MagicMock
    ) -> None:
        """Test that removing unique_together is ignored."""
        operation = migrations.AlterUniqueTogether(
            name="user",
            unique_together=set(),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_other_operations(
        self, rule: AlterUniqueTogetherRule, mock_migration: MagicMock
    ) -> None:
        """Test that other operations are ignored."""
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_get_suggestion(self, rule: AlterUniqueTogetherRule) -> None:
        """Test that suggestion mentions UniqueConstraint."""
        operation = migrations.AlterUniqueTogether(
            name="user",
            unique_together={("email", "tenant_id")},
        )

        suggestion = rule.get_suggestion(operation)

        assert "UniqueConstraint" in suggestion
        assert "AddConstraint" in suggestion


class TestAddCheckConstraintRule:
    """Tests for SM017: AddCheckConstraint rule."""

    @pytest.fixture
    def rule(self) -> AddCheckConstraintRule:
        """Create rule instance."""
        return AddCheckConstraintRule()

    @pytest.fixture
    def mock_migration(self) -> MagicMock:
        """Create a mock migration."""
        migration = MagicMock()
        migration.app_label = "testapp"
        migration.name = "0001_initial"
        return migration

    def test_detects_check_constraint(
        self, rule: AddCheckConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that adding a check constraint is detected."""
        operation = migrations.AddConstraint(
            model_name="order",
            constraint=get_check_constraint(
                check=models.Q(amount__gte=0),
                name="positive_amount",
            ),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is not None
        assert issue.rule_id == "SM017"
        assert "positive_amount" in issue.message
        assert "validate" in issue.message.lower()

    def test_ignores_unique_constraint(
        self, rule: AddCheckConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that unique constraints are ignored."""
        operation = migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=["email"],
                name="unique_email",
            ),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_ignores_other_operations(
        self, rule: AddCheckConstraintRule, mock_migration: MagicMock
    ) -> None:
        """Test that other operations are ignored."""
        operation = migrations.AddField(
            model_name="order",
            name="amount",
            field=models.DecimalField(max_digits=10, decimal_places=2),
        )

        issue = rule.check(operation, mock_migration)

        assert issue is None

    def test_get_suggestion(self, rule: AddCheckConstraintRule) -> None:
        """Test that suggestion mentions NOT VALID."""
        operation = migrations.AddConstraint(
            model_name="order",
            constraint=get_check_constraint(
                check=models.Q(amount__gte=0),
                name="positive_amount",
            ),
        )

        suggestion = rule.get_suggestion(operation)

        assert "NOT VALID" in suggestion
        assert "VALIDATE CONSTRAINT" in suggestion

    def test_applies_to_postgresql(self, rule: AddCheckConstraintRule) -> None:
        """Test that rule applies to PostgreSQL."""
        assert rule.applies_to_db("postgresql") is True

    def test_does_not_apply_to_sqlite(self, rule: AddCheckConstraintRule) -> None:
        """Test that rule does not apply to SQLite."""
        assert rule.applies_to_db("sqlite") is False
