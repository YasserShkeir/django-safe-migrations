"""Tests for the migrate-blocking system check (BLOCK_UNSAFE)."""

from __future__ import annotations

from unittest.mock import patch

from django.test import override_settings

from django_safe_migrations.checks import check_migration_safety
from django_safe_migrations.rules.base import Issue, Severity

_ERROR = Issue(
    rule_id="SM001",
    severity=Severity.ERROR,
    operation="op",
    message="bad",
    app_label="a",
    migration_name="0002",
)
_WARNING = Issue(
    rule_id="SM002", severity=Severity.WARNING, operation="op", message="meh"
)


class TestMigrationSafetyCheck:
    """Tests for check_migration_safety."""

    def test_disabled_by_default(self):
        """With BLOCK_UNSAFE unset, the check returns nothing (and is cheap)."""
        with override_settings(SAFE_MIGRATIONS={}):
            assert check_migration_safety() == []

    def test_reports_only_errors_when_enabled(self):
        """When enabled, only ERROR-level issues become check Errors."""
        with override_settings(SAFE_MIGRATIONS={"BLOCK_UNSAFE": True}):
            with patch(
                "django_safe_migrations.analyzer.MigrationAnalyzer.analyze_all",
                return_value=[_ERROR, _WARNING],
            ):
                messages = check_migration_safety()

        assert len(messages) == 1
        assert messages[0].id == "safe_migrations.SM001"
        assert messages[0].is_serious()

    def test_never_crashes_on_analyzer_error(self):
        """The check must never break the command that triggered it."""
        with override_settings(SAFE_MIGRATIONS={"BLOCK_UNSAFE": True}):
            with patch(
                "django_safe_migrations.analyzer.MigrationAnalyzer.analyze_all",
                side_effect=RuntimeError("boom"),
            ):
                assert check_migration_safety() == []
