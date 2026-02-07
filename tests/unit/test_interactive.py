"""Tests for interactive mode."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from django_safe_migrations.interactive import review_issues_interactively
from django_safe_migrations.rules.base import Issue, Severity


@pytest.fixture
def sample_issues():
    """Create sample issues for interactive review tests."""
    return [
        Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="Adding NOT NULL field without default",
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
            message="Dropping column",
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
            app_label="otherapp",
            migration_name="0001_initial",
        ),
    ]


class TestReviewIssuesInteractively:
    """Tests for review_issues_interactively."""

    def test_empty_issues(self):
        """Test that empty issues returns empty list without prompting."""
        result = review_issues_interactively([])
        assert result == []

    def test_keep_all(self, sample_issues):
        """Test keeping all issues via 'k' input."""
        with patch("builtins.input", side_effect=["k", "k", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3
        assert result == sample_issues

    def test_skip_all(self, sample_issues):
        """Test skipping all issues via 's' input."""
        with patch("builtins.input", side_effect=["s", "s", "s"]):
            result = review_issues_interactively(sample_issues)

        assert result == []

    def test_keep_some_skip_some(self, sample_issues):
        """Test keeping some and skipping others."""
        with patch("builtins.input", side_effect=["k", "s", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 2
        assert result[0].rule_id == "SM001"
        assert result[1].rule_id == "SM010"

    def test_quit_keeps_remaining(self, sample_issues):
        """Test that quit keeps the current and remaining issues."""
        with patch("builtins.input", side_effect=["s", "q"]):
            result = review_issues_interactively(sample_issues)

        # First issue skipped, quit on second -> second and third kept
        assert len(result) == 2
        assert result[0].rule_id == "SM002"
        assert result[1].rule_id == "SM010"

    def test_quit_on_first_keeps_all(self, sample_issues):
        """Test that quitting on the first issue keeps everything."""
        with patch("builtins.input", side_effect=["q"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3

    def test_fix_suggestion_then_keep(self, sample_issues):
        """Test viewing a fix suggestion then keeping the issue."""
        # 'f' shows suggestion, then 'k' keeps it
        with patch("builtins.input", side_effect=["f", "k", "k", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3

    def test_fix_suggestion_then_skip(self, sample_issues):
        """Test viewing a fix suggestion then skipping the issue."""
        with patch("builtins.input", side_effect=["f", "s", "k", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 2
        assert result[0].rule_id == "SM002"

    def test_fix_suggestion_no_suggestion_available(self, sample_issues):
        """Test that 'f' on an issue with no suggestion shows fallback message."""
        # Second issue has no suggestion
        with patch("builtins.input", side_effect=["k", "f", "k", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3

    def test_invalid_choice_reprompts(self, sample_issues):
        """Test that invalid input causes re-prompting."""
        # 'x' is invalid, then 'k' is valid
        with patch("builtins.input", side_effect=["x", "k", "k", "k"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3

    def test_multiple_invalid_then_valid(self, sample_issues):
        """Test multiple invalid inputs before a valid choice."""
        with patch(
            "builtins.input",
            side_effect=["invalid", "bad", "k", "k", "k"],
        ):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 3

    def test_eof_error_keeps_remaining(self, sample_issues):
        """Test that EOFError keeps current and remaining issues."""
        with patch("builtins.input", side_effect=["k", EOFError]):
            result = review_issues_interactively(sample_issues)

        # First kept, then EOFError on second -> second and third kept
        assert len(result) == 3

    def test_keyboard_interrupt_keeps_remaining(self, sample_issues):
        """Test that KeyboardInterrupt keeps current and remaining issues."""
        with patch("builtins.input", side_effect=["s", KeyboardInterrupt]):
            result = review_issues_interactively(sample_issues)

        # First skipped, KeyboardInterrupt on second -> second and third kept
        assert len(result) == 2

    def test_case_insensitive_input(self, sample_issues):
        """Test that uppercase input is accepted."""
        with patch("builtins.input", side_effect=["K", "S", "K"]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 2

    def test_whitespace_stripped_from_input(self, sample_issues):
        """Test that leading/trailing whitespace in input is handled."""
        with patch("builtins.input", side_effect=["  k  ", " s ", " k "]):
            result = review_issues_interactively(sample_issues)

        assert len(result) == 2

    def test_single_issue_keep(self):
        """Test interactive review with a single issue."""
        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="test",
            app_label="myapp",
            migration_name="0001",
        )
        with patch("builtins.input", return_value="k"):
            result = review_issues_interactively([issue])

        assert len(result) == 1
        assert result[0] is issue

    def test_single_issue_skip(self):
        """Test interactive review skipping a single issue."""
        issue = Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="test",
            app_label="myapp",
            migration_name="0001",
        )
        with patch("builtins.input", return_value="s"):
            result = review_issues_interactively([issue])

        assert result == []
