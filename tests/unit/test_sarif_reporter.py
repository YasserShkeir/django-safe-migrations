"""Tests for SARIF reporter."""

from __future__ import annotations

import json
from io import StringIO

from django_safe_migrations.reporters.sarif import SarifReporter
from django_safe_migrations.rules.base import Issue, Severity


class TestSarifReporter:
    """Tests for SarifReporter class."""

    def test_empty_issues(self) -> None:
        """Test SARIF output with no issues."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        reporter.report([])

        output = stream.getvalue()
        data = json.loads(output)

        assert data["version"] == "2.1.0"
        assert "$schema" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["results"] == []

    def test_single_issue(self) -> None:
        """Test SARIF output with a single issue."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="Adding NOT NULL field 'email' without a default",
            suggestion="Add as nullable first, then backfill",
            file_path="myapp/migrations/0002_add_email.py",
            line_number=15,
            app_label="myapp",
            migration_name="0002_add_email",
        )

        reporter.report([issue])

        output = stream.getvalue()
        data = json.loads(output)

        results = data["runs"][0]["results"]
        assert len(results) == 1

        result = results[0]
        assert result["ruleId"] == "SM001"
        assert result["level"] == "error"
        assert "NOT NULL" in result["message"]["text"]
        assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 15

    def test_multiple_issues(self) -> None:
        """Test SARIF output with multiple issues."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        issues = [
            Issue(
                rule_id="SM001",
                severity=Severity.ERROR,
                operation="AddField",
                message="Error message",
                file_path="app/migrations/0001.py",
                line_number=10,
            ),
            Issue(
                rule_id="SM002",
                severity=Severity.WARNING,
                operation="RemoveField",
                message="Warning message",
                file_path="app/migrations/0002.py",
                line_number=20,
            ),
            Issue(
                rule_id="SM008",
                severity=Severity.INFO,
                operation="RunPython",
                message="Info message",
                file_path="app/migrations/0003.py",
                line_number=30,
            ),
        ]

        reporter.report(issues)

        output = stream.getvalue()
        data = json.loads(output)

        results = data["runs"][0]["results"]
        assert len(results) == 3
        assert results[0]["level"] == "error"
        assert results[1]["level"] == "warning"
        assert results[2]["level"] == "note"

    def test_tool_descriptor(self) -> None:
        """Test that tool descriptor includes rules."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream, tool_version="0.2.0")

        reporter.report([])

        output = stream.getvalue()
        data = json.loads(output)

        tool = data["runs"][0]["tool"]["driver"]
        assert tool["name"] == "django-safe-migrations"
        assert tool["version"] == "0.2.0"
        assert "rules" in tool
        assert len(tool["rules"]) > 0

        # Check a specific rule
        rule_ids = [r["id"] for r in tool["rules"]]
        assert "SM001" in rule_ids

    def test_severity_mapping(self) -> None:
        """Test severity to SARIF level mapping."""
        from django_safe_migrations.reporters.sarif import _severity_to_sarif_level

        assert _severity_to_sarif_level(Severity.ERROR) == "error"
        assert _severity_to_sarif_level(Severity.WARNING) == "warning"
        assert _severity_to_sarif_level(Severity.INFO) == "note"

    def test_pretty_output(self) -> None:
        """Test that pretty output is properly formatted."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream, pretty=True)

        reporter.report([])

        output = stream.getvalue()
        # Pretty output should have newlines and indentation
        assert "\n" in output
        assert "  " in output  # Indentation

    def test_compact_output(self) -> None:
        """Test that compact output has no formatting."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream, pretty=False)

        reporter.report([])

        output = stream.getvalue()
        # Compact output should be a single line
        assert "\n" not in output.strip()

    def test_issue_without_location(self) -> None:
        """Test SARIF output for issue without file/line info."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        issue = Issue(
            rule_id="SM007",
            severity=Severity.WARNING,
            operation="RunSQL",
            message="RunSQL without reverse",
        )

        reporter.report([issue])

        output = stream.getvalue()
        data = json.loads(output)

        result = data["runs"][0]["results"][0]
        assert result["ruleId"] == "SM007"
        assert "locations" not in result  # No location info

    def test_fix_suggestion_included(self) -> None:
        """Test that fix suggestions are included in output."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField",
            message="Adding NOT NULL without default",
            suggestion="Add as nullable first, then add NOT NULL constraint",
            file_path="app/migrations/0001.py",
            line_number=10,
        )

        reporter.report([issue])

        output = stream.getvalue()
        data = json.loads(output)

        result = data["runs"][0]["results"][0]
        assert "fixes" in result
        assert "nullable" in result["fixes"][0]["description"]["text"]

    def test_valid_sarif_schema(self) -> None:
        """Test that output conforms to SARIF schema structure."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField",
            message="Test message",
            file_path="app/migrations/0001.py",
            line_number=10,
        )

        reporter.report([issue])

        output = stream.getvalue()
        data = json.loads(output)

        # Check required SARIF 2.1.0 fields
        assert data["version"] == "2.1.0"
        assert "$schema" in data
        assert "runs" in data
        assert len(data["runs"]) >= 1

        run = data["runs"][0]
        assert "tool" in run
        assert "results" in run

        tool = run["tool"]
        assert "driver" in tool
        assert "name" in tool["driver"]
        assert "version" in tool["driver"]
