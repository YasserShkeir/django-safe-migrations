"""Tests for the lint-on-makemigrations command wrapper."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

from django_safe_migrations.management.commands.makemigrations import Command
from django_safe_migrations.rules.base import Issue, Severity

_ERROR = Issue(
    rule_id="SM001",
    severity=Severity.ERROR,
    operation="op",
    message="bad",
    app_label="a",
    migration_name="0002",
)


class TestLintOnMakemigrations:
    """Tests for the post-generation lint."""

    def test_warns_on_issues(self):
        """Detected issues are printed (warn-only by default)."""
        buf = StringIO()
        cmd = Command(stdout=buf)
        with patch(
            "django_safe_migrations.analyzer."
            "MigrationAnalyzer.analyze_new_migrations",
            return_value=[_ERROR],
        ):
            cmd._lint_migrations(strict=False)
        assert "SM001" in buf.getvalue()

    def test_strict_exits_on_errors(self):
        """--lint-strict exits non-zero when there are ERROR-level issues."""
        cmd = Command(stdout=StringIO(), stderr=StringIO())
        with patch(
            "django_safe_migrations.analyzer."
            "MigrationAnalyzer.analyze_new_migrations",
            return_value=[_ERROR],
        ):
            with pytest.raises(SystemExit):
                cmd._lint_migrations(strict=True)

    def test_no_issues_does_not_exit(self):
        """No issues means no output and no exit, even in strict mode."""
        buf = StringIO()
        cmd = Command(stdout=buf)
        with patch(
            "django_safe_migrations.analyzer."
            "MigrationAnalyzer.analyze_new_migrations",
            return_value=[],
        ):
            cmd._lint_migrations(strict=True)
        assert buf.getvalue() == ""

    def test_falls_back_to_analyze_all_without_db(self):
        """If analyze_new_migrations fails (no DB), it falls back to analyze_all."""
        buf = StringIO()
        cmd = Command(stdout=buf)
        with (
            patch(
                "django_safe_migrations.analyzer."
                "MigrationAnalyzer.analyze_new_migrations",
                side_effect=RuntimeError("no db"),
            ),
            patch(
                "django_safe_migrations.analyzer.MigrationAnalyzer.analyze_all",
                return_value=[_ERROR],
            ),
        ):
            cmd._lint_migrations(strict=False)
        assert "SM001" in buf.getvalue()
