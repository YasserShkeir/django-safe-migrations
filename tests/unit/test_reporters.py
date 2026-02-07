"""Tests for reporters."""

import json
from io import StringIO

import pytest

from django_safe_migrations.reporters import get_reporter
from django_safe_migrations.reporters.console import ConsoleReporter
from django_safe_migrations.reporters.github import GitHubReporter
from django_safe_migrations.reporters.gitlab import GitLabReporter
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
        assert "Suggestion:" not in output

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


class TestConsoleReporterUnicode:
    """Tests for ConsoleReporter Unicode detection and fallbacks."""

    def test_unicode_mode_uses_unicode_symbols(self, sample_issues):
        """Test that Unicode mode uses Unicode severity symbols."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False, use_unicode=True)
        output = reporter.report(sample_issues)

        # Unicode symbols
        assert "\u2716" in output  # ✖ for ERROR
        assert "\u2500" in output  # ─ separator

    def test_ascii_mode_uses_ascii_symbols(self, sample_issues):
        """Test that ASCII mode uses ASCII severity symbols."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False, use_unicode=False)
        output = reporter.report(sample_issues)

        assert "X ERROR" in output
        assert "! WARNING" in output
        # Should use ASCII separator
        assert "---" in output

    def test_ascii_no_issues_message(self):
        """Test ASCII fallback for the no-issues checkmark."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False, use_unicode=False)
        output = reporter.report([])

        assert "* No migration issues found" in output

    def test_unicode_no_issues_message(self):
        """Test Unicode checkmark in no-issues message."""
        stream = StringIO()
        reporter = ConsoleReporter(stream=stream, use_color=False, use_unicode=True)
        output = reporter.report([])

        assert "\u2713" in output  # ✓

    def test_ascii_suggestion_symbol(self, sample_issues):
        """Test ASCII fallback for suggestion hint symbol."""
        stream = StringIO()
        reporter = ConsoleReporter(
            stream=stream, use_color=False, use_unicode=False, show_suggestions=True
        )
        output = reporter.report(sample_issues)

        assert "* Suggestion:" in output

    def test_detect_unicode_support_returns_bool(self):
        """Test that _detect_unicode_support returns a boolean."""
        result = ConsoleReporter._detect_unicode_support()
        assert isinstance(result, bool)


class TestGitHubReporterEscaping:
    """Tests for GitHubReporter special character escaping."""

    def test_escapes_percent_in_message(self):
        """Test that % is escaped to %25 in message."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        issue = Issue(
            rule_id="SM024",
            severity=Severity.WARNING,
            operation="RunSQL",
            message="SQL contains %s placeholder",
        )
        output = reporter.report([issue])

        assert "%25s" in output

    def test_escapes_newline_in_message(self):
        """Test that newlines are escaped in message."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        issue = Issue(
            rule_id="SM024",
            severity=Severity.WARNING,
            operation="RunSQL",
            message="Line one\nLine two",
        )
        output = reporter.report([issue])

        assert "%0A" in output

    def test_escapes_percent_in_title(self):
        """Test that % is escaped in title parameter."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        issue = Issue(
            rule_id="SM024",
            severity=Severity.WARNING,
            operation="RunSQL(100% done)",
            message="test",
        )
        output = reporter.report([issue])

        assert "title=[SM024] RunSQL(100%25 done)" in output

    def test_handles_none_operation_in_title(self):
        """Test that None operation doesn't crash title formatting."""
        stream = StringIO()
        reporter = GitHubReporter(stream=stream)
        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation=None,
            message="test message",
        )
        output = reporter.report([issue])

        assert "title=[SM001]" in output
        assert "None" not in output.split("title=")[1].split("::")[0]


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

    def test_get_gitlab_reporter(self):
        """Test getting GitLab reporter."""
        reporter = get_reporter("gitlab")
        assert isinstance(reporter, GitLabReporter)

    def test_invalid_format(self):
        """Test that invalid format raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_reporter("invalid")

        assert "Unknown format" in str(exc_info.value)


class TestGitLabReporter:
    """Tests for GitLabReporter."""

    def test_produces_valid_json(self, sample_issues):
        """Test that output is valid JSON."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        assert isinstance(data, list)

    def test_correct_number_of_entries(self, sample_issues):
        """Test that the number of entries matches the number of issues."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        assert len(data) == 3

    def test_entry_has_required_fields(self, sample_issues):
        """Test that each entry has the required Code Quality fields."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        required_keys = {
            "type",
            "check_name",
            "description",
            "categories",
            "severity",
            "fingerprint",
            "location",
        }
        for entry in data:
            assert required_keys.issubset(entry.keys())

    def test_type_is_issue(self, sample_issues):
        """Test that type field is 'issue' for all entries."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        for entry in data:
            assert entry["type"] == "issue"

    def test_check_name_is_rule_id(self, sample_issues):
        """Test that check_name maps to the rule_id."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        check_names = [e["check_name"] for e in data]
        assert "SM001" in check_names
        assert "SM002" in check_names
        assert "SM010" in check_names

    def test_severity_mapping_error(self):
        """Test that ERROR severity maps to 'critical'."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="test error",
        )
        output = reporter.report([issue])

        data = json.loads(output)
        assert data[0]["severity"] == "critical"

    def test_severity_mapping_warning(self):
        """Test that WARNING severity maps to 'major'."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        issue = Issue(
            rule_id="SM002",
            severity=Severity.WARNING,
            operation="RemoveField(user.old)",
            message="test warning",
        )
        output = reporter.report([issue])

        data = json.loads(output)
        assert data[0]["severity"] == "major"

    def test_severity_mapping_info(self):
        """Test that INFO severity maps to 'minor'."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        issue = Issue(
            rule_id="SM003",
            severity=Severity.INFO,
            operation="SomeOp",
            message="info message",
        )
        output = reporter.report([issue])

        data = json.loads(output)
        assert data[0]["severity"] == "minor"

    def test_fingerprint_is_stable(self, sample_issues):
        """Test that the same issue produces the same fingerprint."""
        stream1 = StringIO()
        reporter1 = GitLabReporter(stream=stream1)
        output1 = reporter1.report(sample_issues)

        stream2 = StringIO()
        reporter2 = GitLabReporter(stream=stream2)
        output2 = reporter2.report(sample_issues)

        data1 = json.loads(output1)
        data2 = json.loads(output2)

        for e1, e2 in zip(data1, data2):
            assert e1["fingerprint"] == e2["fingerprint"]

    def test_fingerprints_are_unique(self, sample_issues):
        """Test that different issues produce different fingerprints."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        fingerprints = [e["fingerprint"] for e in data]
        assert len(fingerprints) == len(set(fingerprints))

    def test_location_has_path(self, sample_issues):
        """Test that location contains the file path."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        # First issue has a file_path
        assert data[0]["location"]["path"] == "myapp/migrations/0002_add_email.py"

    def test_location_has_line_number(self, sample_issues):
        """Test that location contains the line number."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        # First issue has line_number=15
        assert data[0]["location"]["lines"]["begin"] == 15

    def test_missing_file_path_uses_unknown(self):
        """Test that missing file_path defaults to 'unknown'."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        issue = Issue(
            rule_id="SM002",
            severity=Severity.WARNING,
            operation="RemoveField(user.old)",
            message="test",
            file_path=None,
        )
        output = reporter.report([issue])

        data = json.loads(output)
        assert data[0]["location"]["path"] == "unknown"

    def test_missing_line_number_defaults_to_one(self):
        """Test that missing line_number defaults to 1."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        issue = Issue(
            rule_id="SM002",
            severity=Severity.WARNING,
            operation="RemoveField(user.old)",
            message="test",
            line_number=None,
        )
        output = reporter.report([issue])

        data = json.loads(output)
        assert data[0]["location"]["lines"]["begin"] == 1

    def test_categories_is_migration_safety(self, sample_issues):
        """Test that categories contains 'Migration Safety'."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        for entry in data:
            assert "Migration Safety" in entry["categories"]

    def test_empty_issues(self):
        """Test output with no issues produces empty JSON array."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report([])

        data = json.loads(output)
        assert data == []

    def test_description_matches_message(self, sample_issues):
        """Test that entry description matches the issue message."""
        stream = StringIO()
        reporter = GitLabReporter(stream=stream)
        output = reporter.report(sample_issues)

        data = json.loads(output)
        assert data[0]["description"] == "Adding NOT NULL field 'email' without default"
