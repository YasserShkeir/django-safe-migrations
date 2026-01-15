"""Tests for reporters."""

import json
from io import StringIO

import pytest

from django_safe_migrations.reporters import get_reporter
from django_safe_migrations.reporters.console import ConsoleReporter
from django_safe_migrations.reporters.github import GitHubReporter
from django_safe_migrations.reporters.json_reporter import JsonReporter
from django_safe_migrations.rules.base import Issue, Severity


@pytest.fixture
def sample_issues():
    """Create sample issues for testing reporters."""
    return [
        Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="Adding NOT NULL field 'email' without default",
            suggestion="Use nullable field first, then backfill",
            file_path="myapp/migrations/0002_add_email.py",
            line_number=15,
            app_label="myapp",
            migration_name="0002_add_email",
        ),
        Issue(
            rule_id="SM002",
            severity=Severity.WARNING,
            operation="RemoveField(user.old_field)",
            message="Dropping column 'old_field' - ensure code is updated",
            app_label="myapp",
            migration_name="0003_remove_old",
        ),
        Issue(
            rule_id="SM010",
            severity=Severity.ERROR,
            operation="AddIndex(user_email_idx)",
            message="Index creation will lock the table",
            file_path="myapp/migrations/0004_add_index.py",
            line_number=10,
        ),
    ]


class TestConsoleReporter:
    """Tests for ConsoleReporter."""

    def test_reports_issues(self, sample_issues):
        """Test that console reporter outputs issues."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False)
        output = reporter.report(sample_issues)

        assert "SM001" in output
        assert "SM002" in output
        assert "SM010" in output
        assert "ERROR" in output
        assert "WARNING" in output

    def test_reports_no_issues(self):
        """Test output when no issues found."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False)
        output = reporter.report([])

        assert "No migration issues found" in output

    def test_shows_suggestions(self, sample_issues):
        """Test that suggestions are shown."""
        stream = StringIO()
        reporter = ConsoleReporter(
            stream=stream, use_color=False, show_suggestions=True
        )
        output = reporter.report(sample_issues)

        assert "Suggestion" in output
        assert "backfill" in output

    def test_hides_suggestions(self, sample_issues):
        """Test that suggestions can be hidden."""
        stream = StringIO()
        reporter = ConsoleReporter(
            stream=stream, use_color=False, show_suggestions=False
        )
        output = reporter.report(sample_issues)

        # Suggestion text should not appear
        assert "💡 Suggestion:" not in output

    def test_summary(self, sample_issues):
        """Test that summary is included."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False)
        output = reporter.report(sample_issues)

        assert "2 error(s)" in output
        assert "1 warning(s)" in output


class TestJsonReporter:
    """Tests for JsonReporter."""

    def test_valid_json_output(self, sample_issues):
        """Test that output is valid JSON."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream)
        output = reporter.report(sample_issues)

        # Should parse without error
        data = json.loads(output)
        assert "issues" in data
        assert "total" in data
        assert "summary" in data

    def test_issue_count(self, sample_issues):
        """Test that issue count is correct."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        assert data["total"] == 3
        assert len(data["issues"]) == 3

    def test_summary_counts(self, sample_issues):
        """Test that summary counts are correct."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        assert data["summary"]["errors"] == 2
        assert data["summary"]["warnings"] == 1

    def test_pretty_output(self, sample_issues):
        """Test pretty-printed JSON."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream, pretty=True)
        output = reporter.report(sample_issues)

        # Pretty output should have newlines and indentation
        assert "\n" in output
        assert "  " in output

    def test_empty_issues(self):
        """Test output with no issues."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream)
        output = reporter.report([])

        data = json.loads(output)
        assert data["total"] == 0
        assert len(data["issues"]) == 0


class TestGitHubReporter:
    """Tests for GitHubReporter."""

    def test_github_annotations(self, sample_issues):
        """Test that GitHub workflow commands are generated."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        output = reporter.report(sample_issues)

        assert "::error" in output
        assert "::warning" in output
        assert "file=" in output
        assert "line=" in output

    def test_no_issues_notice(self):
        """Test output when no issues found."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        output = reporter.report([])

        assert "::notice::No migration issues found" in output

    def test_group_formatting(self, sample_issues):
        """Test that issues are grouped."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        output = reporter.report(sample_issues)

        assert "::group::" in output
        assert "::endgroup::" in output


class TestGetReporter:
    """Tests for get_reporter factory function."""

    def test_get_console_reporter(self):
        """Test getting console reporter."""
        reporter = get_reporter("console")
        assert isinstance(reporter, ConsoleReporter)

    def test_get_json_reporter(self):
        """Test getting JSON reporter."""
        reporter = get_reporter("json")
        assert isinstance(reporter, JsonReporter)

    def test_get_github_reporter(self):
        """Test getting GitHub reporter."""
        reporter = get_reporter("github")
        assert isinstance(reporter, GitHubReporter)

    def test_invalid_format(self):
        """Test that invalid format raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_reporter("invalid")

        assert "Unknown format" in str(exc_info.value)
