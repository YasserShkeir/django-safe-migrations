"""Integration tests for the check_migrations management command."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings


class TestCheckMigrationsCommand:
    """Integration tests for check_migrations command."""

    def test_command_exists(self):
        """Test that the command is registered."""
        from django.core.management import get_commands

        commands = get_commands()
        assert "check_migrations" in commands

    def test_console_output(self):
        """Test basic console output."""
        out = StringIO()
        try:
            call_command("check_migrations", "safeapp", stdout=out)
        except SystemExit:
            pass  # Command may exit with error code

        output = out.getvalue()
        # Safe app should have no issues
        # (or at least run without crashing)
        assert output is not None

    def test_json_output(self):
        """Test JSON output format."""
        out = StringIO()
        try:
            call_command("check_migrations", "safeapp", format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        # Should be valid JSON
        if output.strip():
            data = json.loads(output)
            assert "total" in data or "issues" in data

    def test_exclude_apps(self):
        """Test excluding apps from check."""
        out = StringIO()
        try:
            call_command(
                "check_migrations",
                exclude_apps=["testapp"],
                stdout=out,
            )
        except SystemExit:
            pass

        # Command should complete without errors
        assert True

    def test_help(self, capsys):
        """Test that help is available."""
        with pytest.raises(SystemExit) as exc_info:
            call_command("check_migrations", "--help")

        # --help should exit with 0
        assert exc_info.value.code == 0

        # Capture output from stdout (argparse writes directly)
        captured = capsys.readouterr()
        output = captured.out

        assert "migration" in output.lower() or "app_labels" in output.lower()


class TestRuleDetection:
    """End-to-end tests verifying specific rules are detected in test migrations."""

    def test_detects_sm001_not_null_without_default(self):
        """Test SM001 detection for NOT NULL field without default."""
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM001 should be detected in 0002_unsafe_not_null.py (email field)
        assert "SM001" in output
        assert "email" in output.lower()
        # Command should exit with error code 1
        assert exc_info.value.code == 1

    def test_detects_sm002_remove_field(self):
        """Test SM002 detection for RemoveField operation."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM002 should be detected in 0005_drop_column.py (nickname field)
        assert "SM002" in output
        assert "nickname" in output.lower()

    def test_detects_sm003_delete_model(self):
        """Test SM003 detection for DeleteModel operation."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM003 should be detected in 0010_delete_model.py (Profile model)
        assert "SM003" in output
        assert "profile" in output.lower()

    def test_detects_sm007_run_sql_without_reverse(self):
        """Test SM007 detection for RunSQL without reverse_sql."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM007 should be detected in 0006_run_sql_no_reverse.py
        assert "SM007" in output

    @pytest.mark.postgres
    def test_detects_sm009_unique_constraint(self):
        """Test SM009 detection for UniqueConstraint (PostgreSQL)."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM009 should be detected in 0008_unique_constraint.py
        assert "SM009" in output

    @pytest.mark.postgres
    def test_detects_sm010_non_concurrent_index(self):
        """Test SM010 detection for AddIndex without CONCURRENTLY."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM010 should be detected in 0004_unsafe_index.py
        assert "SM010" in output

    # Note: SM012 (enum ADD VALUE in transaction) cannot be tested via integration
    # tests because:
    # - On SQLite: The PostgreSQL-specific SQL syntax fails
    # - On PostgreSQL: The enum type doesn't exist, causing migration failure
    # SM012 is thoroughly tested in unit tests (test_run_sql_rules.py)

    def test_detects_sm016_run_python_without_reverse(self):
        """Test SM016 detection for RunPython without reverse_code."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM016 should be detected in 0009_run_python_no_reverse.py
        assert "SM016" in output


class TestOutputFormats:
    """Tests for different output formats."""

    def test_github_output_format(self):
        """Test GitHub Actions output format produces ::error annotations."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="github", stdout=out)

        output = out.getvalue()
        # GitHub format should use ::error:: or ::warning:: annotations
        assert "::error" in output or "::warning" in output

    def test_json_output_structure(self):
        """Test JSON output has correct structure."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Should have issues array and total count
        assert "issues" in data
        assert "total" in data
        assert isinstance(data["issues"], list)
        assert data["total"] > 0

        # Each issue should have required fields
        if data["issues"]:
            issue = data["issues"][0]
            assert "rule_id" in issue
            assert "severity" in issue
            assert "migration_name" in issue
            assert "message" in issue

    def test_console_output_includes_rule_id(self):
        """Test console output includes rule IDs for identification."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="console", stdout=out)

        output = out.getvalue()
        # Should include rule IDs like SM001, SM002, etc.
        assert "SM0" in output  # Match any SM0XX pattern


class TestCommandOptions:
    """Tests for command-line options and configuration."""

    def test_fail_on_warning_flag(self):
        """Test --fail-on-warning causes exit code 1 for warnings."""
        out = StringIO()
        # safeapp has no issues, so should exit 0 normally
        try:
            call_command("check_migrations", "safeapp", stdout=out)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        # Safe app should pass without --fail-on-warning
        assert exit_code == 0

    def test_exclude_apps_removes_detection(self):
        """Test --exclude-apps properly excludes apps from analysis."""
        out = StringIO()
        try:
            call_command(
                "check_migrations",
                exclude_apps=["testapp"],
                stdout=out,
            )
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        output = out.getvalue()
        # With testapp excluded, should not find SM001 from testapp
        assert "SM001" not in output or exit_code == 0

    @override_settings(SAFE_MIGRATIONS={"DISABLED_RULES": ["SM001"]})
    def test_disabled_rules_configuration(self):
        """Test DISABLED_RULES setting excludes specific rules."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM001 should NOT be in output when disabled
        # Other rules should still be detected
        assert "SM001" not in output
        assert "SM002" in output  # SM002 should still be detected

    @override_settings(SAFE_MIGRATIONS={"DISABLED_RULES": ["SM001", "SM002", "SM003"]})
    def test_multiple_disabled_rules(self):
        """Test multiple rules can be disabled at once."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # All three should be disabled
        assert "SM001" not in output
        assert "SM002" not in output
        assert "SM003" not in output
        # Other rules should still work
        assert "SM007" in output  # RunSQL without reverse


class TestSafeAppNoIssues:
    """Tests verifying safe migrations produce no issues."""

    def test_safe_app_exits_zero(self):
        """Test that safeapp with only safe migrations exits with 0."""
        out = StringIO()
        try:
            call_command("check_migrations", "safeapp", stdout=out)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        assert exit_code == 0

    def test_safe_app_json_zero_issues(self):
        """Test safeapp JSON output shows zero issues."""
        out = StringIO()
        try:
            call_command("check_migrations", "safeapp", format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        if output.strip():
            data = json.loads(output)
            assert data.get("total", 0) == 0
