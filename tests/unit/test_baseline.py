"""Tests for baseline support."""

from __future__ import annotations

import json

import pytest

from django_safe_migrations.baseline import (
    filter_baselined_issues,
    generate_baseline,
    load_baseline,
)
from django_safe_migrations.rules.base import Issue, Severity


@pytest.fixture
def sample_issues():
    """Create sample issues for baseline tests."""
    return [
        Issue(
            rule_id="SM001",
            severity=Severity.ERROR,
            operation="AddField(user.email)",
            message="Adding NOT NULL field without default",
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
            app_label="otherapp",
            migration_name="0001_initial",
        ),
    ]


class TestGenerateBaseline:
    """Tests for generate_baseline."""

    def test_generates_file(self, tmp_path, sample_issues):
        """Test that a baseline file is created on disk."""
        baseline_path = str(tmp_path / "baseline.json")
        count = generate_baseline(sample_issues, baseline_path)

        assert count == 3
        assert (tmp_path / "baseline.json").exists()

    def test_baseline_is_valid_json(self, tmp_path, sample_issues):
        """Test that the generated file contains valid JSON."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)

        text = (tmp_path / "baseline.json").read_text(encoding="utf-8")
        data = json.loads(text)

        assert "version" in data
        assert "count" in data
        assert "issues" in data

    def test_baseline_version_is_one(self, tmp_path, sample_issues):
        """Test that the baseline version is 1."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)

        data = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
        assert data["version"] == 1

    def test_baseline_count_matches(self, tmp_path, sample_issues):
        """Test that count in baseline matches the number of issues."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)

        data = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
        assert data["count"] == 3
        assert len(data["issues"]) == 3

    def test_baseline_entries_have_correct_keys(self, tmp_path, sample_issues):
        """Test that each entry has the expected keys."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)

        data = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
        for entry in data["issues"]:
            assert "rule_id" in entry
            assert "app_label" in entry
            assert "migration_name" in entry
            assert "operation" in entry

    def test_baseline_preserves_issue_data(self, tmp_path, sample_issues):
        """Test that issue data is preserved in the baseline."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)

        data = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
        first = data["issues"][0]

        assert first["rule_id"] == "SM001"
        assert first["app_label"] == "myapp"
        assert first["migration_name"] == "0002_add_email"
        assert first["operation"] == "AddField(user.email)"

    def test_empty_issues(self, tmp_path):
        """Test generating a baseline with no issues."""
        baseline_path = str(tmp_path / "baseline.json")
        count = generate_baseline([], baseline_path)

        assert count == 0

        data = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
        assert data["count"] == 0
        assert data["issues"] == []

    def test_returns_count(self, tmp_path, sample_issues):
        """Test that generate_baseline returns the number of baselined issues."""
        baseline_path = str(tmp_path / "baseline.json")
        result = generate_baseline(sample_issues, baseline_path)

        assert result == len(sample_issues)


class TestLoadBaseline:
    """Tests for load_baseline."""

    def test_loads_valid_baseline(self, tmp_path):
        """Test loading a valid baseline file."""
        data = {
            "version": 1,
            "count": 2,
            "issues": [
                {
                    "rule_id": "SM001",
                    "app_label": "myapp",
                    "migration_name": "0001_initial",
                    "operation": "AddField(user.email)",
                },
                {
                    "rule_id": "SM002",
                    "app_label": "myapp",
                    "migration_name": "0002_remove",
                    "operation": "RemoveField(user.old)",
                },
            ],
        }
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        entries = load_baseline(str(path))

        assert len(entries) == 2
        assert entries[0]["rule_id"] == "SM001"
        assert entries[1]["rule_id"] == "SM002"

    def test_roundtrip(self, tmp_path, sample_issues):
        """Test that generate then load round-trips correctly."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)
        entries = load_baseline(baseline_path)

        assert len(entries) == len(sample_issues)
        assert entries[0]["rule_id"] == sample_issues[0].rule_id
        assert entries[0]["app_label"] == sample_issues[0].app_label

    def test_file_not_found(self, tmp_path):
        """Test that loading a missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_baseline(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        """Test that loading invalid JSON raises JSONDecodeError."""
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_baseline(str(path))

    def test_unknown_version_still_loads(self, tmp_path):
        """Test that an unknown version logs a warning but still loads."""
        data = {
            "version": 999,
            "issues": [
                {
                    "rule_id": "SM001",
                    "app_label": "app",
                    "migration_name": "0001",
                    "operation": "Op",
                }
            ],
        }
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        entries = load_baseline(str(path))
        assert len(entries) == 1

    def test_missing_issues_key(self, tmp_path):
        """Test that a baseline file without 'issues' returns empty list."""
        data = {"version": 1, "count": 0}
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        entries = load_baseline(str(path))
        assert entries == []


class TestFilterBaselinedIssues:
    """Tests for filter_baselined_issues."""

    def test_filters_matching_issues(self, sample_issues):
        """Test that issues matching the baseline are removed."""
        baseline = [
            {
                "rule_id": "SM001",
                "app_label": "myapp",
                "migration_name": "0002_add_email",
                "operation": "AddField(user.email)",
            },
        ]

        filtered = filter_baselined_issues(sample_issues, baseline)

        assert len(filtered) == 2
        assert all(i.rule_id != "SM001" for i in filtered)

    def test_keeps_non_matching_issues(self, sample_issues):
        """Test that issues not in the baseline are kept."""
        baseline = [
            {
                "rule_id": "SM999",
                "app_label": "noapp",
                "migration_name": "0099_fake",
                "operation": "FakeOp",
            },
        ]

        filtered = filter_baselined_issues(sample_issues, baseline)
        assert len(filtered) == 3

    def test_empty_baseline(self, sample_issues):
        """Test that an empty baseline keeps all issues."""
        filtered = filter_baselined_issues(sample_issues, [])
        assert len(filtered) == len(sample_issues)

    def test_empty_issues(self):
        """Test that empty issues returns empty list."""
        baseline = [
            {
                "rule_id": "SM001",
                "app_label": "myapp",
                "migration_name": "0001",
                "operation": "Op",
            }
        ]
        filtered = filter_baselined_issues([], baseline)
        assert filtered == []

    def test_filters_multiple_matching(self, sample_issues):
        """Test filtering when multiple issues match the baseline."""
        baseline = [
            {
                "rule_id": "SM001",
                "app_label": "myapp",
                "migration_name": "0002_add_email",
                "operation": "AddField(user.email)",
            },
            {
                "rule_id": "SM010",
                "app_label": "otherapp",
                "migration_name": "0001_initial",
                "operation": "AddIndex(user_email_idx)",
            },
        ]

        filtered = filter_baselined_issues(sample_issues, baseline)

        assert len(filtered) == 1
        assert filtered[0].rule_id == "SM002"

    def test_matching_requires_all_four_fields(self, sample_issues):
        """Test that partial match does not filter an issue."""
        # Same rule_id and app_label, but different migration_name
        baseline = [
            {
                "rule_id": "SM001",
                "app_label": "myapp",
                "migration_name": "DIFFERENT_MIGRATION",
                "operation": "AddField(user.email)",
            },
        ]

        filtered = filter_baselined_issues(sample_issues, baseline)
        assert len(filtered) == 3  # Nothing filtered

    def test_full_roundtrip_filter(self, tmp_path, sample_issues):
        """Test generate -> load -> filter roundtrip."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)
        baseline = load_baseline(baseline_path)

        # All issues should be filtered since baseline matches all
        filtered = filter_baselined_issues(sample_issues, baseline)
        assert filtered == []

    def test_new_issue_not_in_baseline(self, tmp_path, sample_issues):
        """Test that a new issue introduced after baseline is kept."""
        baseline_path = str(tmp_path / "baseline.json")
        generate_baseline(sample_issues, baseline_path)
        baseline = load_baseline(baseline_path)

        new_issue = Issue(
            rule_id="SM005",
            severity=Severity.ERROR,
            operation="RenameField(user.name)",
            message="New issue not in baseline",
            app_label="newapp",
            migration_name="0001_new",
        )
        all_issues = sample_issues + [new_issue]

        filtered = filter_baselined_issues(all_issues, baseline)
        assert len(filtered) == 1
        assert filtered[0].rule_id == "SM005"
