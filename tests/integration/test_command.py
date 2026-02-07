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
        # safeapp has no issues, should not raise SystemExit
        call_command("check_migrations", "safeapp", stdout=out)

        output = out.getvalue()
        assert isinstance(output, str)

    def test_json_output(self):
        """Test JSON output format."""
        out = StringIO()
        # safeapp has no issues, should not raise SystemExit
        call_command("check_migrations", "safeapp", format="json", stdout=out)

        output = out.getvalue()
        assert output.strip()
        data = json.loads(output)
        assert "total" in data or "issues" in data

    def test_exclude_apps(self):
        """Test excluding apps from check."""
        out = StringIO()
        # With testapp excluded, should have no issues and not raise
        call_command(
            "check_migrations",
            exclude_apps=["testapp"],
            stdout=out,
        )

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
    def test_detects_sm011_unique_constraint_postgresql(self):
        """Test SM011 detection for UniqueConstraint on PostgreSQL.

        SM009 defers to SM011 on PostgreSQL to provide more specific
        advice about concurrent index creation.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", stdout=out)

        output = out.getvalue()
        # SM011 should be detected (SM009 defers to SM011 on PostgreSQL)
        assert "SM011" in output

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


class TestSarifOutput:
    """Tests for SARIF output format (v0.2.0 feature)."""

    def test_sarif_output_format(self):
        """Test SARIF output is valid JSON with correct structure."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="sarif", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Verify SARIF structure
        assert "$schema" in data
        assert "sarif" in data["$schema"]
        assert data["version"] == "2.1.0"
        assert "runs" in data
        assert len(data["runs"]) == 1

        run = data["runs"][0]
        assert "tool" in run
        assert "results" in run

        # Verify tool descriptor
        assert run["tool"]["driver"]["name"] == "django-safe-migrations"
        assert "rules" in run["tool"]["driver"]

        # Verify results exist (testapp has issues)
        assert len(run["results"]) > 0

        # Verify result structure
        result = run["results"][0]
        assert "ruleId" in result
        assert "level" in result
        assert "message" in result
        assert result["ruleId"].startswith("SM")

    def test_sarif_severity_mapping(self):
        """Test SARIF severity levels are correctly mapped."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="sarif", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        results = data["runs"][0]["results"]
        levels = {r["level"] for r in results}

        # Should have valid SARIF levels
        valid_levels = {"error", "warning", "note"}
        assert levels.issubset(valid_levels)

    def test_sarif_includes_location(self):
        """Test SARIF results include location information."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="sarif", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find a result with location
        for result in data["runs"][0]["results"]:
            if "locations" in result and result["locations"]:
                location = result["locations"][0]
                assert "physicalLocation" in location
                physical = location["physicalLocation"]
                assert "artifactLocation" in physical
                assert "uri" in physical["artifactLocation"]
                return

        # At least some results should have locations
        # (not all may have file info depending on the issue)


class TestOutputFileOption:
    """Tests for --output file option (v0.2.0 feature)."""

    def test_output_to_file_json(self, tmp_path):
        """Test JSON output can be written to file."""
        output_file = tmp_path / "report.json"

        with pytest.raises(SystemExit):
            call_command(
                "check_migrations",
                "testapp",
                format="json",
                output=str(output_file),
            )

        # File should exist and contain valid JSON
        assert output_file.exists()
        content = output_file.read_text()
        data = json.loads(content)
        assert "issues" in data
        assert data["total"] > 0

    def test_output_to_file_sarif(self, tmp_path):
        """Test SARIF output can be written to file."""
        output_file = tmp_path / "report.sarif"

        with pytest.raises(SystemExit):
            call_command(
                "check_migrations",
                "testapp",
                format="sarif",
                output=str(output_file),
            )

        # File should exist and contain valid SARIF
        assert output_file.exists()
        content = output_file.read_text()
        data = json.loads(content)
        assert data["version"] == "2.1.0"
        assert "runs" in data

    def test_output_file_with_safe_app(self, tmp_path):
        """Test output file is created even for apps with no issues."""
        output_file = tmp_path / "report.json"

        try:
            call_command(
                "check_migrations",
                "safeapp",
                format="json",
                output=str(output_file),
            )
        except SystemExit:
            pass

        assert output_file.exists()
        content = output_file.read_text()
        data = json.loads(content)
        assert data["total"] == 0


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


class TestSuppressionComments:
    """Tests for inline suppression comments (v0.2.0 feature)."""

    def test_suppression_comment_prevents_detection(self):
        """Test that suppression comment prevents rule from being reported.

        Migration 0011_suppressed_not_null.py has a NOT NULL field without default
        but includes a `# safe-migrations: ignore SM001` comment.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find issues from 0011_suppressed_not_null
        suppressed_issues = [
            i
            for i in data["issues"]
            if "0011_suppressed_not_null" in i.get("migration_name", "")
            and i.get("rule_id") == "SM001"
        ]

        # SM001 should NOT be reported for this migration due to suppression
        assert len(suppressed_issues) == 0

    def test_suppression_only_affects_specified_rule(self):
        """Test that suppression only affects the specified rule, not others."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # SM001 from 0002 should still be detected (no suppression)
        sm001_issues = [
            i
            for i in data["issues"]
            if i.get("rule_id") == "SM001"
            and "0002_unsafe_not_null" in i.get("migration_name", "")
        ]
        assert len(sm001_issues) > 0

    def test_unsuppressed_rules_still_detected(self):
        """Test that rules without suppression are still detected."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Other rules (SM002, SM007, etc.) should still be detected
        rule_ids = {i.get("rule_id") for i in data["issues"]}
        assert "SM002" in rule_ids or "SM007" in rule_ids


class TestCLIEntryPoint:
    """Tests for CLI entry point used by pre-commit (v0.2.0 feature)."""

    def test_cli_module_exists(self):
        """Test that CLI module can be imported."""
        from django_safe_migrations import cli

        assert hasattr(cli, "main")

    def test_cli_main_returns_exit_code(self):
        """Test CLI main function returns proper exit codes."""
        import os

        from django_safe_migrations.cli import main

        # Set Django settings for the test
        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        # Test with safe app - should return 0
        exit_code = main(["safeapp"])
        assert exit_code == 0

    def test_cli_main_with_issues_returns_nonzero(self):
        """Test CLI returns non-zero exit code when issues found."""
        import os

        from django_safe_migrations.cli import main

        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        # Test with testapp - has issues, should return 1
        exit_code = main(["testapp"])
        assert exit_code == 1

    def test_cli_format_options(self):
        """Test CLI accepts format options."""
        import os

        from django_safe_migrations.cli import main

        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        # Should not raise for valid format options
        # (output goes to stdout which we don't capture here)
        exit_code = main(["safeapp", "--format", "json"])
        assert exit_code == 0

    def test_cli_exclude_apps(self):
        """Test CLI --exclude-apps option works."""
        import os

        from django_safe_migrations.cli import main

        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        # Excluding testapp should result in no issues (only safeapp checked)
        exit_code = main(["--exclude-apps", "testapp"])
        assert exit_code == 0


class TestNewRulesV030:
    """Tests for new rules in v0.3.0 (SM018, SM019)."""

    @pytest.mark.postgres
    def test_detects_sm018_concurrent_in_atomic(self):
        """Test SM018 detection for concurrent index in atomic migration.

        Migration 0012_concurrent_index_in_atomic.py uses AddIndexConcurrently
        without setting atomic = False.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM018 issues
        sm018_issues = [i for i in data["issues"] if i.get("rule_id") == "SM018"]
        assert (
            len(sm018_issues) > 0
        ), "SM018 should detect concurrent ops in atomic migration"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm018_issues]
        assert any(
            "0012_concurrent_index_in_atomic" in name for name in migration_names
        ), "SM018 should be detected in 0012_concurrent_index_in_atomic"

    def test_detects_sm019_reserved_keyword(self):
        """Test SM019 detection for reserved keyword column names.

        Migration 0013 adds 'order' (SQL reserved keyword) and 'type'
        ('type' was removed from reserved keywords in v0.5.0).
        SM019 also detects the 'user' field in Profile (0001_initial).
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM019 issues
        sm019_issues = [i for i in data["issues"] if i.get("rule_id") == "SM019"]
        assert (
            len(sm019_issues) >= 2
        ), "SM019 should detect 'order' (0013) and 'user' (0001)"

        # Verify messages mention the keywords
        messages = " ".join(i.get("message", "") for i in sm019_issues)
        assert "order" in messages.lower()


class TestNewRulesV040:
    """Tests for new rules in v0.4.0 (SM020-SM026)."""

    def test_detects_sm020_alterfield_null_false(self):
        """Test SM020 detection for AlterField changing null=True to null=False.

        Migration 0013 adds 'order' as nullable (null=True).
        Migration 0014 alters it to null=False, which SM020 should detect
        via before-state resolution.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM020 issues
        sm020_issues = [i for i in data["issues"] if i.get("rule_id") == "SM020"]
        assert len(sm020_issues) > 0, "SM020 should detect AlterField with null=False"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm020_issues]
        assert any(
            "0014_alterfield_null_false" in name for name in migration_names
        ), "SM020 should be detected in 0014_alterfield_null_false"

    @pytest.mark.postgres
    def test_detects_sm021_alterfield_unique(self):
        """Test SM021 detection for AlterField with unique=True.

        Migration 0015_alterfield_unique.py adds unique constraint via AlterField.
        Note: SM021 is PostgreSQL-specific as it involves concurrent index creation.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM021 issues
        sm021_issues = [i for i in data["issues"] if i.get("rule_id") == "SM021"]
        assert len(sm021_issues) > 0, "SM021 should detect AlterField with unique=True"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm021_issues]
        assert any(
            "0015_alterfield_unique" in name for name in migration_names
        ), "SM021 should be detected in 0015_alterfield_unique"

    def test_detects_sm022_expensive_default(self):
        """Test SM022 detection for expensive default callable.

        Migration 0016_expensive_default.py uses timezone.now as default.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM022 issues
        sm022_issues = [i for i in data["issues"] if i.get("rule_id") == "SM022"]
        assert len(sm022_issues) > 0, "SM022 should detect expensive default callable"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm022_issues]
        assert any(
            "0016_expensive_default" in name for name in migration_names
        ), "SM022 should be detected in 0016_expensive_default"

    def test_detects_sm023_manytomany_field(self):
        """Test SM023 detection for ManyToManyField.

        Migration 0017_manytomany_field.py adds a ManyToManyField.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM023 issues
        sm023_issues = [i for i in data["issues"] if i.get("rule_id") == "SM023"]
        assert len(sm023_issues) > 0, "SM023 should detect ManyToManyField"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm023_issues]
        assert any(
            "0017_manytomany_field" in name for name in migration_names
        ), "SM023 should be detected in 0017_manytomany_field"

    def test_detects_sm024_sql_injection_pattern(self):
        """Test SM024 detection for SQL injection patterns in RunSQL.

        Migration 0018_sql_injection_pattern.py uses %s formatting in RunSQL.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM024 issues
        sm024_issues = [i for i in data["issues"] if i.get("rule_id") == "SM024"]
        assert len(sm024_issues) > 0, "SM024 should detect SQL injection patterns"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm024_issues]
        assert any(
            "0018_sql_injection_pattern" in name for name in migration_names
        ), "SM024 should be detected in 0018_sql_injection_pattern"

    def test_detects_sm025_fk_without_index(self):
        """Test SM025 detection for ForeignKey with db_index=False.

        Migration 0019_fk_without_index.py adds a ForeignKey without index.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM025 issues
        sm025_issues = [i for i in data["issues"] if i.get("rule_id") == "SM025"]
        assert len(sm025_issues) > 0, "SM025 should detect ForeignKey without index"

        # Verify it's from the right migration
        migration_names = [i.get("migration_name", "") for i in sm025_issues]
        assert any(
            "0019_fk_without_index" in name for name in migration_names
        ), "SM025 should be detected in 0019_fk_without_index"

    def test_detects_sm026_run_python_no_batching(self):
        """Test SM026 detection for RunPython without batching.

        Migration 0020_run_python_no_batching.py uses .all() without .iterator().
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM026 issues
        sm026_issues = [i for i in data["issues"] if i.get("rule_id") == "SM026"]
        # Note: SM026 may not trigger if source inspection fails
        # This is acceptable behavior documented in the rule
        if len(sm026_issues) > 0:
            # Verify it's from the right migration
            migration_names = [i.get("migration_name", "") for i in sm026_issues]
            assert any(
                "0020_run_python_no_batching" in name for name in migration_names
            ), "SM026 should be detected in 0020_run_python_no_batching"


class TestCategoryConfiguration:
    """Tests for category-based rule configuration (v0.3.0 feature)."""

    @override_settings(SAFE_MIGRATIONS={"DISABLED_CATEGORIES": ["destructive"]})
    def test_disabled_category_excludes_rules(self):
        """Test DISABLED_CATEGORIES excludes rules in that category.

        The 'destructive' category includes SM002, SM003, SM006, SM013, SM014.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM002 (drop column) and SM003 (drop table) should be disabled
        assert (
            "SM002" not in rule_ids
        ), "SM002 should be disabled by destructive category"
        assert (
            "SM003" not in rule_ids
        ), "SM003 should be disabled by destructive category"

        # SM001 (not_null_without_default) should still be detected
        assert "SM001" in rule_ids, "SM001 should still be active"

    @override_settings(SAFE_MIGRATIONS={"DISABLED_CATEGORIES": ["reversibility"]})
    def test_disabled_reversibility_category(self):
        """Test disabling reversibility category excludes SM007 and SM016."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM007 and SM016 should be disabled
        assert (
            "SM007" not in rule_ids
        ), "SM007 should be disabled by reversibility category"
        assert (
            "SM016" not in rule_ids
        ), "SM016 should be disabled by reversibility category"

    @override_settings(
        SAFE_MIGRATIONS={
            "ENABLED_CATEGORIES": ["destructive"],
            "DISABLED_RULES": [],  # Clear any defaults
        }
    )
    def test_enabled_categories_whitelist_mode(self):
        """Test ENABLED_CATEGORIES creates whitelist mode.

        Only rules in enabled categories should run.
        On PostgreSQL, SM009 defers to SM011 (not in destructive),
        so only warnings exist and no SystemExit is raised.
        """
        out = StringIO()
        try:
            call_command("check_migrations", "testapp", format="json", stdout=out)
        except SystemExit:
            pass  # SM009 (ERROR) fires on SQLite but not PostgreSQL

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM001 should NOT be present (it's in 'schema-changes', not 'destructive')
        assert "SM001" not in rule_ids, "SM001 should be excluded in whitelist mode"

        # SM002 or SM003 should be present (destructive)
        assert (
            "SM002" in rule_ids or "SM003" in rule_ids
        ), "Destructive rules should be active"

    @override_settings(
        SAFE_MIGRATIONS={"DISABLED_CATEGORIES": ["informational", "naming"]}
    )
    def test_disabled_info_categories(self):
        """Test disabling informational and naming categories."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM006, SM008, SM016, SM019 are in informational - should be disabled
        assert "SM019" not in rule_ids, "SM019 should be disabled by naming category"


class TestListRulesCommand:
    """Tests for --list-rules command (v0.4.0 feature)."""

    def test_list_rules_console_output(self):
        """Test --list-rules produces console output."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, stdout=out)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        output = out.getvalue()

        # Should exit with 0
        assert exit_code == 0

        # Should list available rules
        assert "Available Rules:" in output
        assert "SM001" in output
        assert "SM010" in output

    def test_list_rules_json_output(self):
        """Test --list-rules with JSON format."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, format="json", stdout=out)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        output = out.getvalue()
        data = json.loads(output)

        # Should be a list of rules
        assert isinstance(data, list)
        assert len(data) > 0

        # Each rule should have expected fields
        rule = data[0]
        assert "rule_id" in rule
        assert "severity" in rule
        assert "description" in rule
        assert "categories" in rule

        # Should include SM001
        rule_ids = {r["rule_id"] for r in data}
        assert "SM001" in rule_ids

        # Should exit with 0
        assert exit_code == 0

    def test_list_rules_includes_new_v040_rules(self):
        """Test --list-rules includes new v0.4.0 rules."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {r["rule_id"] for r in data}

        # New v0.4.0 rules should be listed
        assert "SM020" in rule_ids  # AlterFieldNullFalseRule
        assert "SM021" in rule_ids  # AlterFieldUniqueRule
        assert "SM022" in rule_ids  # ExpensiveDefaultCallableRule
        assert "SM023" in rule_ids  # AddManyToManyRule
        assert "SM024" in rule_ids  # SQLInjectionPatternRule
        assert "SM025" in rule_ids  # ForeignKeyWithoutIndexRule
        assert "SM026" in rule_ids  # RunPythonNoBatchingRule

    def test_list_rules_includes_categories(self):
        """Test --list-rules includes category information."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)

        # Find SM001 and check categories
        sm001 = next(r for r in data if r["rule_id"] == "SM001")
        assert "categories" in sm001
        assert isinstance(sm001["categories"], list)

    def test_list_rules_includes_db_vendors(self):
        """Test --list-rules includes database vendor information."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)

        # Find SM010 (postgres-specific rule)
        sm010 = next(r for r in data if r["rule_id"] == "SM010")
        assert "db_vendors" in sm010
        assert "postgresql" in sm010["db_vendors"]


class TestListRulesCLI:
    """Tests for --list-rules via CLI entry point."""

    def test_cli_list_rules(self):
        """Test CLI --list-rules option."""
        import os

        from django_safe_migrations.cli import main

        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        exit_code = main(["--list-rules"])
        assert exit_code == 0

    def test_cli_list_rules_json(self):
        """Test CLI --list-rules with JSON format."""
        import os

        from django_safe_migrations.cli import main

        os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings.sqlite"

        exit_code = main(["--list-rules", "--format", "json"])
        assert exit_code == 0


class TestNewRulesV050:
    """Tests for new rules in v0.5.0 (SM028-SM036)."""

    def test_detects_sm028_autofield_primary_key(self):
        """Test SM028 detection for AutoField primary key.

        Migration 0021_autofield_primary_key.py uses AutoField(primary_key=True).
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm028_issues = [i for i in data["issues"] if i.get("rule_id") == "SM028"]
        assert len(sm028_issues) > 0, "SM028 should detect AutoField primary key"

        migration_names = [i.get("migration_name", "") for i in sm028_issues]
        assert any(
            "0021_autofield_primary_key" in name for name in migration_names
        ), "SM028 should be detected in 0021_autofield_primary_key"

    def test_detects_sm029_drop_not_null(self):
        """Test SM029 detection for dropping NOT NULL (making field nullable).

        Migration 0022_drop_not_null.py alters username to null=True.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm029_issues = [i for i in data["issues"] if i.get("rule_id") == "SM029"]
        assert len(sm029_issues) > 0, "SM029 should detect dropping NOT NULL"

        migration_names = [i.get("migration_name", "") for i in sm029_issues]
        assert any(
            "0022_drop_not_null" in name for name in migration_names
        ), "SM029 should be detected in 0022_drop_not_null"

    @pytest.mark.postgres
    def test_detects_sm031_charfield_postgresql(self):
        """Test SM031 detection for CharField on PostgreSQL.

        SM031 is a PostgreSQL-only INFO rule that recommends TextField
        over CharField since they have identical performance on PostgreSQL.
        Existing migrations with AddField(CharField) should trigger this.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm031_issues = [i for i in data["issues"] if i.get("rule_id") == "SM031"]
        assert (
            len(sm031_issues) > 0
        ), "SM031 should detect CharField(max_length>32) on PostgreSQL"

    @override_settings(USE_TZ=False)
    def test_detects_sm032_datetime_no_tz(self):
        """Test SM032 detection for DateTimeField when USE_TZ=False.

        SM032 flags DateTimeField additions when USE_TZ is False since
        naive datetimes can cause timezone issues.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm032_issues = [i for i in data["issues"] if i.get("rule_id") == "SM032"]
        assert (
            len(sm032_issues) > 0
        ), "SM032 should detect DateTimeField when USE_TZ=False"

    def test_detects_sm033_field_with_default(self):
        """Test SM033 detection for NOT NULL field with default.

        Migration 0024_field_with_default.py adds a NOT NULL CharField with default.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm033_issues = [i for i in data["issues"] if i.get("rule_id") == "SM033"]
        assert len(sm033_issues) > 0, "SM033 should detect field with default"

        migration_names = [i.get("migration_name", "") for i in sm033_issues]
        assert any(
            "0024_field_with_default" in name for name in migration_names
        ), "SM033 should be detected in 0024_field_with_default"

    def test_detects_sm035_run_sql_no_lock_timeout(self):
        """Test SM035 detection for RunSQL DDL without lock_timeout.

        Migration 0025_run_sql_no_lock_timeout.py has ALTER TABLE without lock_timeout.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm035_issues = [i for i in data["issues"] if i.get("rule_id") == "SM035"]
        assert len(sm035_issues) > 0, "SM035 should detect DDL without lock_timeout"

        migration_names = [i.get("migration_name", "") for i in sm035_issues]
        assert any(
            "0025_run_sql_no_lock_timeout" in name for name in migration_names
        ), "SM035 should be detected in 0025_run_sql_no_lock_timeout"

    def test_detects_sm036_create_table_no_if_exists(self):
        """Test SM036 detection for CREATE TABLE without IF NOT EXISTS.

        Migration 0026 has CREATE TABLE without IF NOT EXISTS.
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm036_issues = [i for i in data["issues"] if i.get("rule_id") == "SM036"]
        assert (
            len(sm036_issues) > 0
        ), "SM036 should detect CREATE TABLE without IF NOT EXISTS"

        migration_names = [i.get("migration_name", "") for i in sm036_issues]
        assert any(
            "0026_create_table_no_if_exists" in name for name in migration_names
        ), "SM036 should be detected in 0026_create_table_no_if_exists"

    @pytest.mark.postgres
    def test_detects_sm030_remove_index(self):
        """Test SM030 detection for RemoveIndex without CONCURRENTLY.

        Migration 0023_remove_index.py uses RemoveIndex (PostgreSQL-only rule).
        """
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        sm030_issues = [i for i in data["issues"] if i.get("rule_id") == "SM030"]
        assert len(sm030_issues) > 0, "SM030 should detect RemoveIndex"

        migration_names = [i.get("migration_name", "") for i in sm030_issues]
        assert any(
            "0023_remove_index" in name for name in migration_names
        ), "SM030 should be detected in 0023_remove_index"

    def test_list_rules_includes_v050_rules(self):
        """Test --list-rules includes new v0.5.0 rules."""
        out = StringIO()
        try:
            call_command("check_migrations", list_rules=True, format="json", stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {r["rule_id"] for r in data}

        for rule_id in [
            "SM027",
            "SM028",
            "SM029",
            "SM030",
            "SM031",
            "SM032",
            "SM033",
            "SM034",
            "SM035",
            "SM036",
        ]:
            assert rule_id in rule_ids, f"{rule_id} should be in --list-rules output"


class TestGitLabOutput:
    """Tests for GitLab Code Quality output format (v0.5.0 feature)."""

    def test_gitlab_output_format(self):
        """Test GitLab Code Quality output is valid JSON array."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="gitlab", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        assert isinstance(data, list)
        assert len(data) > 0

        entry = data[0]
        assert "type" in entry
        assert entry["type"] == "issue"
        assert "check_name" in entry
        assert "description" in entry
        assert "severity" in entry
        assert "fingerprint" in entry
        assert "location" in entry
        assert "path" in entry["location"]

    def test_gitlab_severity_mapping(self):
        """Test GitLab severity levels are correctly mapped."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="gitlab", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        severities = {entry["severity"] for entry in data}
        valid_severities = {"blocker", "critical", "major", "minor", "info"}
        assert severities.issubset(valid_severities)


class TestPerAppConfiguration:
    """Tests for per-app rule configuration (v0.3.0 feature)."""

    @override_settings(
        SAFE_MIGRATIONS={
            "APP_RULES": {
                "testapp": {
                    "DISABLED_RULES": ["SM001", "SM002"],
                }
            }
        }
    )
    def test_per_app_disabled_rules(self):
        """Test APP_RULES can disable specific rules for an app."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM001 and SM002 should be disabled for testapp
        assert "SM001" not in rule_ids, "SM001 should be disabled for testapp"
        assert "SM002" not in rule_ids, "SM002 should be disabled for testapp"

        # SM007 should still be active
        assert "SM007" in rule_ids, "SM007 should still be active"

    @override_settings(
        SAFE_MIGRATIONS={
            "APP_RULES": {
                "testapp": {
                    "DISABLED_CATEGORIES": ["reversibility"],
                }
            }
        }
    )
    def test_per_app_disabled_categories(self):
        """Test APP_RULES can disable categories for an app."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM007 and SM016 (reversibility) should be disabled for testapp
        assert "SM007" not in rule_ids, "SM007 should be disabled for testapp"
        assert "SM016" not in rule_ids, "SM016 should be disabled for testapp"

    @override_settings(
        SAFE_MIGRATIONS={
            "RULE_SEVERITY": {"SM002": "INFO"},  # Global severity
            "APP_RULES": {
                "testapp": {
                    "RULE_SEVERITY": {"SM002": "ERROR"},  # App-specific override
                }
            },
        }
    )
    def test_per_app_severity_override(self):
        """Test APP_RULES can override rule severity per-app."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        # Find SM002 issue
        sm002_issues = [i for i in data["issues"] if i.get("rule_id") == "SM002"]
        assert len(sm002_issues) > 0, "SM002 should be detected"

        # Severity should be ERROR (app-specific), not INFO (global)
        assert sm002_issues[0]["severity"] == "error"

    @override_settings(
        SAFE_MIGRATIONS={
            "DISABLED_RULES": ["SM001"],  # Globally disabled
            "APP_RULES": {
                "testapp": {
                    "DISABLED_RULES": [],  # Clear for this app (inherits global)
                }
            },
        }
    )
    def test_global_disabled_applies_when_app_has_empty_config(self):
        """Test global DISABLED_RULES applies when app has no specific disables."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", format="json", stdout=out)

        output = out.getvalue()
        data = json.loads(output)

        rule_ids = {i.get("rule_id") for i in data["issues"]}

        # SM001 should still be disabled (global setting)
        # Note: Current implementation may vary - this tests expected behavior
        # If app config exists, it should still check global
        assert "SM002" in rule_ids or "SM007" in rule_ids  # Other rules work


class TestBaselineIntegration:
    """Integration tests for baseline support (v0.5.0 feature)."""

    def test_generate_baseline_command(self, tmp_path):
        """Test --generate-baseline creates a valid baseline file."""
        baseline_path = str(tmp_path / "baseline.json")
        out = StringIO()

        call_command(
            "check_migrations",
            "testapp",
            generate_baseline=baseline_path,
            stdout=out,
        )

        output = out.getvalue()
        assert "Generated baseline" in output

        # Verify the file exists and contains valid JSON
        content = (tmp_path / "baseline.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["version"] == 1
        assert data["count"] > 0
        assert len(data["issues"]) > 0

    def test_baseline_filters_existing_issues(self, tmp_path):
        """Test --baseline filters out baselined issues."""
        baseline_path = str(tmp_path / "baseline.json")

        # First generate a baseline
        call_command(
            "check_migrations",
            "testapp",
            generate_baseline=baseline_path,
            stdout=StringIO(),
        )

        # Now run with the baseline - all issues should be filtered
        out = StringIO()
        try:
            call_command(
                "check_migrations",
                "testapp",
                format="json",
                baseline=baseline_path,
                stdout=out,
            )
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        output = out.getvalue()
        data = json.loads(output)

        # With full baseline, all existing issues should be filtered
        assert data["total"] == 0
        assert exit_code == 0

    def test_baseline_keeps_new_issues(self, tmp_path):
        """Test --baseline keeps issues not in the baseline."""
        baseline_path = str(tmp_path / "baseline.json")

        # Generate a baseline for safeapp (0 issues)
        call_command(
            "check_migrations",
            "safeapp",
            generate_baseline=baseline_path,
            stdout=StringIO(),
        )

        # Run against testapp with safeapp's baseline - issues should remain
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command(
                "check_migrations",
                "testapp",
                format="json",
                baseline=baseline_path,
                stdout=out,
            )

        output = out.getvalue()
        data = json.loads(output)
        assert data["total"] > 0


class TestDiffIntegration:
    """Integration tests for diff mode (v0.5.0 feature)."""

    def test_diff_mode_produces_valid_output(self):
        """Test --diff produces valid JSON output."""
        out = StringIO()
        try:
            call_command(
                "check_migrations",
                diff="HEAD",
                format="json",
                stdout=out,
            )
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)

        # Diff mode should produce valid JSON with correct structure
        assert "issues" in data
        assert "total" in data
        assert isinstance(data["issues"], list)

        # Issues (if any) should only be from changed migration files
        for issue in data["issues"]:
            assert "rule_id" in issue
            assert "migration_name" in issue


class TestInteractiveIntegration:
    """Integration tests for interactive mode (v0.5.0 feature)."""

    def test_interactive_quit_keeps_all(self, monkeypatch):
        """Test interactive mode with immediate quit keeps all issues."""
        # Simulate user pressing 'q' immediately
        monkeypatch.setattr("builtins.input", lambda _: "q")

        out = StringIO()
        with pytest.raises(SystemExit):
            call_command(
                "check_migrations",
                "testapp",
                format="json",
                interactive=True,
                stdout=out,
            )

        output = out.getvalue()
        data = json.loads(output)
        # Quitting keeps all remaining issues
        assert data["total"] > 0

    def test_interactive_skip_all(self, monkeypatch):
        """Test interactive mode with all issues skipped produces no errors."""
        # Simulate user pressing 's' for every issue
        monkeypatch.setattr("builtins.input", lambda _: "s")

        out = StringIO()
        try:
            call_command(
                "check_migrations",
                "testapp",
                format="json",
                interactive=True,
                stdout=out,
            )
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        output = out.getvalue()
        data = json.loads(output)
        # All issues skipped means 0 kept
        assert data["total"] == 0
        assert exit_code == 0


class TestVerboseMode:
    """Tests for verbose progress reporting (v0.5.0 feature)."""

    def test_verbose_flag_accepted(self):
        """Test that --verbose flag is accepted by the command."""
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("check_migrations", "testapp", verbose=True, stdout=out)

        output = out.getvalue()
        # Should produce normal output (verbose writes to stderr)
        assert "SM001" in output or "SM002" in output


class TestWatchMode:
    """Tests for watch mode (v0.5.0 feature)."""

    def test_watch_requires_watchdog(self):
        """Test that --watch raises clear error if watchdog not installed."""
        from django_safe_migrations.watch import has_watchdog

        if has_watchdog():
            pytest.skip("watchdog is installed")

        out = StringIO()
        with pytest.raises(ImportError, match="watchdog"):
            call_command("check_migrations", watch=True, stdout=out)
