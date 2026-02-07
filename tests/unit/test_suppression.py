"""Tests for inline suppression comment parsing."""

from __future__ import annotations

import logging
import tempfile

from django_safe_migrations.suppression import (
    Suppression,
    get_suppressions_from_file,
    is_operation_suppressed,
    parse_suppression_comment,
)


class TestParseSuppressionComment:
    """Tests for parse_suppression_comment function."""

    def test_single_rule(self) -> None:
        """Test parsing a single rule suppression."""
        line = "# safe-migrations: ignore SM001"
        result = parse_suppression_comment(line, 10)

        assert result is not None
        assert result.rules == {"SM001"}
        assert result.reason is None
        assert result.line_number == 10

    def test_multiple_rules(self) -> None:
        """Test parsing multiple rules."""
        line = "# safe-migrations: ignore SM001, SM002, SM003"
        result = parse_suppression_comment(line, 5)

        assert result is not None
        assert result.rules == {"SM001", "SM002", "SM003"}
        assert result.reason is None

    def test_with_reason(self) -> None:
        """Test parsing suppression with reason."""
        line = "# safe-migrations: ignore SM001 -- intentional cleanup"
        result = parse_suppression_comment(line, 1)

        assert result is not None
        assert result.rules == {"SM001"}
        assert result.reason == "intentional cleanup"

    def test_ignore_all(self) -> None:
        """Test parsing 'ignore all' suppression."""
        line = "# safe-migrations: ignore all"
        result = parse_suppression_comment(line, 1)

        assert result is not None
        assert result.rules == {"all"}

    def test_ignore_all_with_reason(self) -> None:
        """Test parsing 'ignore all' with reason."""
        line = "# safe-migrations: ignore all -- this migration is reviewed"
        result = parse_suppression_comment(line, 1)

        assert result is not None
        assert result.rules == {"all"}
        assert result.reason == "this migration is reviewed"

    def test_case_insensitive(self) -> None:
        """Test that parsing is case-insensitive."""
        line = "# Safe-Migrations: Ignore SM001"
        result = parse_suppression_comment(line, 1)

        assert result is not None
        assert result.rules == {"SM001"}

    def test_no_match(self) -> None:
        """Test that non-suppression lines return None."""
        lines = [
            "# This is a regular comment",
            "migrations.AddField(",
            "# safe-migration: ignore SM001",  # typo: missing 's'
            "",
        ]

        for line in lines:
            assert parse_suppression_comment(line, 1) is None

    def test_inline_comment(self) -> None:
        """Test parsing inline comment on same line as code."""
        line = "    ),  # safe-migrations: ignore SM002"
        result = parse_suppression_comment(line, 15)

        assert result is not None
        assert result.rules == {"SM002"}

    def test_rules_normalized_to_uppercase(self) -> None:
        """Test that rule IDs are normalized to uppercase."""
        line = "# safe-migrations: ignore sm001, Sm002"
        result = parse_suppression_comment(line, 1)

        assert result is not None
        assert result.rules == {"SM001", "SM002"}


class TestSuppression:
    """Tests for Suppression dataclass."""

    def test_suppresses_matching_rule(self) -> None:
        """Test suppresses() returns True for matching rule."""
        suppression = Suppression(rules={"SM001", "SM002"}, reason=None, line_number=1)

        assert suppression.suppresses("SM001") is True
        assert suppression.suppresses("SM002") is True

    def test_suppresses_non_matching_rule(self) -> None:
        """Test suppresses() returns False for non-matching rule."""
        suppression = Suppression(rules={"SM001"}, reason=None, line_number=1)

        assert suppression.suppresses("SM002") is False

    def test_suppresses_all(self) -> None:
        """Test suppresses() with 'all' rule."""
        suppression = Suppression(rules={"all"}, reason=None, line_number=1)

        assert suppression.suppresses("SM001") is True
        assert suppression.suppresses("SM999") is True


class TestGetSuppressionsFromFile:
    """Tests for get_suppressions_from_file function."""

    def test_empty_file(self) -> None:
        """Test parsing empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()

            result = get_suppressions_from_file(f.name)
            assert result == {}

    def test_file_with_suppressions(self) -> None:
        """Test parsing file with suppression comments."""
        content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        # safe-migrations: ignore SM001 -- adding nullable first
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.CharField(max_length=255, null=True),
        ),
        # safe-migrations: ignore SM002, SM003
        migrations.RemoveField(
            model_name='user',
            name='old_field',
        ),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            result = get_suppressions_from_file(f.name)

            # Should find two suppressions
            assert len(result) == 2
            # Line 6 has the first suppression
            assert 6 in result
            assert result[6].rules == {"SM001"}
            assert result[6].reason == "adding nullable first"
            # Line 12 has the second suppression
            assert 12 in result
            assert result[12].rules == {"SM002", "SM003"}

    def test_nonexistent_file(self) -> None:
        """Test parsing nonexistent file."""
        result = get_suppressions_from_file("/nonexistent/path/to/file.py")
        assert result == {}


class TestIsOperationSuppressed:
    """Tests for is_operation_suppressed function."""

    def test_suppressed_on_previous_line(self) -> None:
        """Test operation suppressed by comment on previous line."""
        content = """line 1
line 2
# safe-migrations: ignore SM001
migrations.AddField(
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            # Operation on line 4, suppression on line 3
            assert is_operation_suppressed(f.name, 4, "SM001") is True
            assert is_operation_suppressed(f.name, 4, "SM002") is False

    def test_suppressed_on_same_line(self) -> None:
        """Test operation suppressed by inline comment."""
        content = """line 1
line 2
migrations.AddField(  # safe-migrations: ignore SM001
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            assert is_operation_suppressed(f.name, 3, "SM001") is True

    def test_suppressed_two_lines_before(self) -> None:
        """Test operation suppressed by comment two lines before."""
        content = """line 1
# safe-migrations: ignore SM001

migrations.AddField(
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            # Operation on line 4, suppression on line 2 (blank line 3)
            assert is_operation_suppressed(f.name, 4, "SM001") is True

    def test_not_suppressed(self) -> None:
        """Test operation that is not suppressed."""
        content = """line 1
# safe-migrations: ignore SM001
line 3
line 4
migrations.AddField(
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            # Operation on line 5, suppression on line 2 (too far)
            assert is_operation_suppressed(f.name, 5, "SM001") is False

    def test_ignore_all_suppresses_any_rule(self) -> None:
        """Test 'ignore all' suppresses any rule."""
        content = """# safe-migrations: ignore all
migrations.AddField(
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()

            assert is_operation_suppressed(f.name, 2, "SM001") is True
            assert is_operation_suppressed(f.name, 2, "SM999") is True

    def test_with_preloaded_suppressions(self) -> None:
        """Test using preloaded suppressions for efficiency."""
        suppressions = {
            5: Suppression(rules={"SM001"}, reason=None, line_number=5),
        }

        # Using a file path that doesn't exist - should use preloaded
        result = is_operation_suppressed(
            "/fake/path.py",
            6,  # Line after suppression
            "SM001",
            suppressions=suppressions,
        )
        assert result is True


class TestSuppressionValidation:
    """Tests for suppression validation of unknown rule IDs."""

    def test_warns_on_unknown_rule_id(self, caplog) -> None:
        """Test that a warning is logged for unknown rule IDs."""
        with caplog.at_level(logging.WARNING, logger="django_safe_migrations"):
            result = parse_suppression_comment("# safe-migrations: ignore SM999", 10)

        assert result is not None
        assert result.rules == {"SM999"}
        assert "SM999" in caplog.text
        assert "unknown rule" in caplog.text.lower()

    def test_no_warning_for_known_rule(self, caplog) -> None:
        """Test that no warning is logged for known rule IDs."""
        with caplog.at_level(logging.WARNING, logger="django_safe_migrations"):
            result = parse_suppression_comment("# safe-migrations: ignore SM001", 10)

        assert result is not None
        assert "unknown" not in caplog.text.lower()

    def test_no_warning_for_ignore_all(self, caplog) -> None:
        """Test that 'ignore all' does not trigger validation."""
        with caplog.at_level(logging.WARNING, logger="django_safe_migrations"):
            result = parse_suppression_comment("# safe-migrations: ignore all", 10)

        assert result is not None
        assert "unknown" not in caplog.text.lower()

    def test_warns_for_mixed_known_unknown(self, caplog) -> None:
        """Test warning when mixing known and unknown rule IDs."""
        with caplog.at_level(logging.WARNING, logger="django_safe_migrations"):
            result = parse_suppression_comment(
                "# safe-migrations: ignore SM001, SM999", 5
            )

        assert result is not None
        assert result.rules == {"SM001", "SM999"}
        assert "SM999" in caplog.text
        # SM001 should not be in the warning
        assert "SM001" not in caplog.text.split("unknown")[1]
