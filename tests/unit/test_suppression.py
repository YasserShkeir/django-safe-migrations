"""Tests for inline suppression comment parsing."""

from __future__ import annotations

import importlib
import logging
import sys
import tempfile
import uuid

import pytest

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.suppression import (
    Suppression,
    SuppressionScope,
    format_suppression_report,
    get_suppressions_from_file,
    is_migration_suppressed,
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

    def test_migration_scope_single_rule(self) -> None:
        """Test parsing a migration-level suppression."""
        result = parse_suppression_comment(
            "# safe-migrations: ignore-migration SM038 -- intentional mix",
            3,
        )

        assert result is not None
        assert result.scope is SuppressionScope.MIGRATION
        assert result.rules == {"SM038"}
        assert result.reason == "intentional mix"
        assert result.line_number == 3

    def test_operation_scope_remains_default(self) -> None:
        """Test existing ignore syntax remains operation-scoped."""
        result = parse_suppression_comment("# safe-migrations: ignore SM001", 4)

        assert result is not None
        assert result.scope is SuppressionScope.OPERATION
        assert result.rules == {"SM001"}

    def test_migration_scope_multiple_rules_and_all(self) -> None:
        """Test migration scope supports multiple rules and all."""
        multiple = parse_suppression_comment(
            "# safe-migrations: ignore-migration SM038, SM054",
            1,
        )
        all_rules = parse_suppression_comment(
            "# safe-migrations: ignore-migration all",
            2,
        )

        assert multiple is not None
        assert multiple.scope is SuppressionScope.MIGRATION
        assert multiple.rules == {"SM038", "SM054"}
        assert all_rules is not None
        assert all_rules.scope is SuppressionScope.MIGRATION
        assert all_rules.rules == {"all"}


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

    def test_ignores_migration_scope(self) -> None:
        """Test operation suppression ignores migration-level suppressions."""
        suppressions = {
            5: Suppression(
                rules={"SM001"},
                reason=None,
                line_number=5,
                scope=SuppressionScope.MIGRATION,
            ),
        }

        result = is_operation_suppressed(
            "/fake/path.py",
            6,  # Line after suppression
            "SM001",
            suppressions=suppressions,
        )

        assert result is False


class TestIsMigrationSuppressed:
    """Tests for is_migration_suppressed function."""

    def test_matches_migration_scope(self) -> None:
        """Test migration suppression matches regardless of line number."""
        suppressions = {
            2: Suppression(
                rules={"SM038"},
                reason="intentional",
                line_number=2,
                scope=SuppressionScope.MIGRATION,
            ),
        }

        assert is_migration_suppressed("SM038", suppressions) is True
        assert is_migration_suppressed("SM001", suppressions) is False

    def test_ignore_all_matches_any_rule(self) -> None:
        """Test migration-level ignore all suppresses any rule."""
        suppressions = {
            2: Suppression(
                rules={"all"},
                reason=None,
                line_number=2,
                scope=SuppressionScope.MIGRATION,
            ),
        }

        assert is_migration_suppressed("SM038", suppressions) is True
        assert is_migration_suppressed("SM001", suppressions) is True

    def test_ignores_operation_scope(self) -> None:
        """Test migration suppression ignores operation-level suppressions."""
        suppressions = {
            2: Suppression(
                rules={"SM038"},
                reason=None,
                line_number=2,
                scope=SuppressionScope.OPERATION,
            ),
        }

        assert is_migration_suppressed("SM038", suppressions) is False


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


# ---------------------------------------------------------------------------
# Blast-radius regression tests.
#
# ``ignore-migration`` silences a rule for an entire file, so a directive that
# fires from the wrong place turns the whole migration into a blind spot.
# These tests pin down that a directive counts only when it is a real comment
# whose text *starts* with the directive.
# ---------------------------------------------------------------------------

MIGRATION_TEMPLATE = '''{header}

from django.db import migrations, models

{extra}


class Migration(migrations.Migration):
    """A migration with several genuinely unsafe operations."""

    dependencies = []

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255, null=False, default="x"),
        ),
        migrations.RunSQL(sql="UPDATE app_user SET email = 'a@b.c' {sql_extra}"),
        migrations.RemoveField(model_name="user", name="legacy"),
        migrations.RunPython(code=lambda apps, schema_editor: None),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
    ]
'''

PLAIN_HEADER = '"""A migration."""'

REFUSAL_DOCSTRING = '''"""Reviewer notes for this migration.

The team discussed blanket suppression and decided NOT to use
# safe-migrations: ignore-migration all
because it would hide every check in this file.
"""'''


@pytest.fixture
def analyze_migration_source(tmp_path, monkeypatch):
    """Write a migration module to disk, import it and analyse it.

    Returns a callable taking the module source and giving back the
    ``(sorted rule IDs found, analyzer)`` pair. The analyzer is returned so
    tests can inspect ``suppression_records``.
    """
    monkeypatch.syspath_prepend(str(tmp_path))

    def _analyze(source: str, check_reverse: bool = False):
        module_name = f"dsm_suppression_fixture_{uuid.uuid4().hex}"
        (tmp_path / f"{module_name}.py").write_text(source, encoding="utf-8")
        module = importlib.import_module(module_name)
        try:
            migration = module.Migration("0001_test", "testapp")
            analyzer = MigrationAnalyzer(
                db_vendor="postgresql", check_reverse=check_reverse
            )
            issues = analyzer.analyze_migration(
                migration, app_label="testapp", migration_name="0001_test"
            )
            return sorted({issue.rule_id for issue in issues}), analyzer
        finally:
            sys.modules.pop(module_name, None)

    return _analyze


def build_migration(header: str = PLAIN_HEADER, extra: str = "", sql_extra: str = ""):
    """Render a migration module with an optional poisoned fragment."""
    return MIGRATION_TEMPLATE.format(header=header, extra=extra, sql_extra=sql_extra)


class TestSuppressionBlastRadius:
    """A stray occurrence of the phrase must not silence a migration."""

    def test_baseline_migration_reports_issues(self, analyze_migration_source) -> None:
        """The unpoisoned fixture reports several rules (guards the others)."""
        found, _ = analyze_migration_source(build_migration())

        assert len(found) >= 5
        assert {"SM007", "SM016", "SM038"} <= set(found)

    def test_phrase_in_module_docstring_is_ignored(
        self, analyze_migration_source
    ) -> None:
        """A docstring mentioning the directive must not suppress anything.

        Case (a): here the docstring explicitly refuses the directive, so
        honouring it would invert the author's stated intent.
        """
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(header=REFUSAL_DOCSTRING)
        )

        assert found == baseline
        assert analyzer.suppression_records == []

    def test_commented_out_directive_is_ignored(self, analyze_migration_source) -> None:
        """Case (b): a directive commented out with a second '#' must not fire."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(extra="# # safe-migrations: ignore-migration all")
        )

        assert found == baseline
        assert analyzer.suppression_records == []

    def test_phrase_inside_string_literal_is_ignored(
        self, analyze_migration_source
    ) -> None:
        """Case (c): the phrase inside a RunSQL string is data, not a directive."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(sql_extra="-- # safe-migrations: ignore-migration all")
        )

        assert found == baseline
        assert analyzer.suppression_records == []

    def test_phrase_quoted_in_prose_is_ignored(self, analyze_migration_source) -> None:
        """Case (d): the directive quoted in backticks inside a comment."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(
                extra="# never write `# safe-migrations: ignore-migration all` here"
            )
        )

        assert found == baseline
        assert analyzer.suppression_records == []

    def test_real_directive_still_suppresses(self, analyze_migration_source) -> None:
        """A genuine migration-level directive still silences the whole file."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(
                extra="# safe-migrations: ignore-migration all -- reviewed by DBA"
            )
        )

        assert found == []
        assert baseline  # the fixture really did have something to suppress
        assert {r.rule_id for r in analyzer.suppression_records} == set(baseline)

    def test_real_scoped_directive_suppresses_only_named_rule(
        self, analyze_migration_source
    ) -> None:
        """``ignore-migration SM038`` drops SM038 and leaves the rest alone."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(extra="# safe-migrations: ignore-migration SM038")
        )

        assert "SM038" in baseline
        assert found == [rule_id for rule_id in baseline if rule_id != "SM038"]
        assert [r.rule_id for r in analyzer.suppression_records] == ["SM038"]

    def test_unknown_rule_id_fails_safe(self, analyze_migration_source) -> None:
        """An unknown rule ID suppresses nothing rather than everything."""
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(
            build_migration(extra="# safe-migrations: ignore-migration SM999")
        )

        assert found == baseline
        assert analyzer.suppression_records == []

    def test_suppression_report_names_what_was_suppressed(
        self, analyze_migration_source
    ) -> None:
        """The report names each silenced rule and the directive's line."""
        _, analyzer = analyze_migration_source(
            build_migration(
                extra="# safe-migrations: ignore-migration SM038 -- reviewed by DBA"
            )
        )

        report = format_suppression_report(analyzer.suppression_records)

        assert "Suppressed 1 finding(s)" in report
        assert "SM038" in report
        assert "[migration]" in report
        assert "reviewed by DBA" in report
        record = analyzer.suppression_records[0]
        assert f":{record.line_number}" in report
        assert record.file_path is not None
        assert record.app_label == "testapp"

    def test_empty_report_when_nothing_suppressed(
        self, analyze_migration_source
    ) -> None:
        """No suppressions means no report noise."""
        _, analyzer = analyze_migration_source(build_migration())

        assert format_suppression_report(analyzer.suppression_records) == ""

    def test_operation_directive_still_works(self, analyze_migration_source) -> None:
        """Operation-scoped suppression is unaffected by the anchoring fix."""
        source = build_migration().replace(
            '        migrations.RunSQL(sql="UPDATE',
            "        # safe-migrations: ignore SM007 -- reviewed\n"
            '        migrations.RunSQL(sql="UPDATE',
        )
        baseline, _ = analyze_migration_source(build_migration())
        found, analyzer = analyze_migration_source(source)

        assert "SM007" in baseline
        assert "SM007" not in found
        records = [r for r in analyzer.suppression_records if r.rule_id == "SM007"]
        assert records and records[0].scope is SuppressionScope.OPERATION
        assert records[0].reason == "reviewed"

    def test_ignore_migration_all_covers_reverse_rules(
        self, analyze_migration_source
    ) -> None:
        """``all`` also silences RV0xx, matching the documented contract."""
        baseline, _ = analyze_migration_source(build_migration(), check_reverse=True)
        found, analyzer = analyze_migration_source(
            build_migration(extra="# safe-migrations: ignore-migration all"),
            check_reverse=True,
        )

        assert any(rule_id.startswith("RV") for rule_id in baseline)
        assert found == []
        assert any(r.rule_id.startswith("RV") for r in analyzer.suppression_records)


class TestSuppressionAnchoring:
    """Unit-level checks on where a directive is allowed to start."""

    def test_directive_must_start_the_comment(self) -> None:
        """A directive preceded by anything inside the comment is inert."""
        assert parse_suppression_comment("# # safe-migrations: ignore all", 1) is None
        assert (
            parse_suppression_comment("# see `# safe-migrations: ignore all`", 1)
            is None
        )
        assert (
            parse_suppression_comment("# TODO: safe-migrations: ignore all", 1) is None
        )

    def test_trailing_comment_still_parses(self) -> None:
        """A directive after code on the same line remains valid."""
        result = parse_suppression_comment("    ),  # safe-migrations: ignore SM002", 3)

        assert result is not None
        assert result.rules == {"SM002"}

    def test_string_literals_are_skipped(self) -> None:
        """Directives inside strings are not parsed out of a real file."""
        content = (
            '"""Do not use\n'
            "# safe-migrations: ignore-migration all\n"
            'in this project."""\n'
            'SQL = "-- # safe-migrations: ignore-migration all"\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            f.flush()

            assert get_suppressions_from_file(f.name) == {}

    def test_untokenizable_file_falls_back_without_crashing(self) -> None:
        """A syntax error degrades to the anchored line scan, not an exception."""
        content = (
            "def broken(:\n"
            "# safe-migrations: ignore SM001\n"
            "# # safe-migrations: ignore SM002\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            f.flush()

            result = get_suppressions_from_file(f.name)

        assert 2 in result
        assert result[2].rules == {"SM001"}
        # The commented-out directive stays inert in the fallback path too.
        assert 3 not in result
