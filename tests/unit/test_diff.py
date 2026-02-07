"""Tests for diff mode."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from django_safe_migrations.diff import (
    _find_git_root,
    get_changed_apps_and_migrations,
    get_changed_migration_files,
)


class TestFindGitRoot:
    """Tests for _find_git_root."""

    def test_returns_git_root(self):
        """Test that _find_git_root returns the git root path."""
        mock_result = MagicMock()
        mock_result.stdout = "/home/user/project\n"

        with patch("django_safe_migrations.diff.subprocess.run", return_value=mock_result):
            root = _find_git_root()

        assert root == "/home/user/project"

    def test_strips_trailing_whitespace(self):
        """Test that trailing whitespace is stripped from the result."""
        mock_result = MagicMock()
        mock_result.stdout = "/home/user/project  \n"

        with patch("django_safe_migrations.diff.subprocess.run", return_value=mock_result):
            root = _find_git_root()

        assert root == "/home/user/project"

    def test_falls_back_to_cwd_on_error(self):
        """Test that cwd is returned when git is not available."""
        with patch(
            "django_safe_migrations.diff.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            root = _find_git_root()

        assert root == os.getcwd()

    def test_falls_back_to_cwd_on_file_not_found(self):
        """Test that cwd is returned when git binary is not found."""
        with patch(
            "django_safe_migrations.diff.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            root = _find_git_root()

        assert root == os.getcwd()


class TestGetChangedMigrationFiles:
    """Tests for get_changed_migration_files."""

    def test_returns_migration_files(self, tmp_path):
        """Test that changed migration files are returned."""
        # Create mock migration files on disk
        app_dir = tmp_path / "myapp" / "migrations"
        app_dir.mkdir(parents=True)
        migration_file = app_dir / "0002_add_field.py"
        migration_file.write_text("# migration")

        git_diff_output = f"myapp/migrations/0002_add_field.py\n"
        mock_diff_result = MagicMock()
        mock_diff_result.stdout = git_diff_output

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert len(files) == 1
        assert files[0] == str(tmp_path / "myapp" / "migrations" / "0002_add_field.py")

    def test_filters_non_migration_files(self, tmp_path):
        """Test that non-migration files are excluded."""
        # Create a non-migration Python file
        (tmp_path / "myapp").mkdir()
        (tmp_path / "myapp" / "models.py").write_text("# model")

        git_diff_output = "myapp/models.py\nmyapp/views.py\n"
        mock_diff_result = MagicMock()
        mock_diff_result.stdout = git_diff_output

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []

    def test_filters_non_python_files(self, tmp_path):
        """Test that non-Python files in migrations are excluded."""
        app_dir = tmp_path / "myapp" / "migrations"
        app_dir.mkdir(parents=True)
        (app_dir / "README.md").write_text("docs")

        git_diff_output = "myapp/migrations/README.md\n"
        mock_diff_result = MagicMock()
        mock_diff_result.stdout = git_diff_output

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []

    def test_returns_empty_on_git_error(self):
        """Test that an empty list is returned when git diff fails."""
        mock_root_result = MagicMock()
        mock_root_result.stdout = "/tmp\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            raise subprocess.CalledProcessError(1, "git")

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []

    def test_returns_empty_on_file_not_found(self):
        """Test that an empty list is returned when git is not installed."""
        mock_root_result = MagicMock()
        mock_root_result.stdout = "/tmp\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            raise FileNotFoundError("git not found")

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []

    def test_uses_custom_base_ref(self, tmp_path):
        """Test that the base_ref parameter is passed to git diff."""
        app_dir = tmp_path / "myapp" / "migrations"
        app_dir.mkdir(parents=True)
        (app_dir / "0001_initial.py").write_text("# migration")

        mock_diff_result = MagicMock()
        mock_diff_result.stdout = "myapp/migrations/0001_initial.py\n"

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            get_changed_migration_files("develop")

        # Check that the diff command used "develop" as the base ref
        diff_cmd = [c for c in calls if "diff" in c]
        assert any("develop" in cmd for cmd in diff_cmd)

    def test_skips_nonexistent_files(self, tmp_path):
        """Test that files listed by git but missing from disk are skipped."""
        git_diff_output = "myapp/migrations/0002_missing.py\n"
        mock_diff_result = MagicMock()
        mock_diff_result.stdout = git_diff_output

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []

    def test_handles_empty_git_output(self, tmp_path):
        """Test handling of empty git diff output."""
        mock_diff_result = MagicMock()
        mock_diff_result.stdout = ""

        mock_root_result = MagicMock()
        mock_root_result.stdout = str(tmp_path) + "\n"

        def mock_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return mock_root_result
            return mock_diff_result

        with patch("django_safe_migrations.diff.subprocess.run", side_effect=mock_run):
            files = get_changed_migration_files("main")

        assert files == []


class TestGetChangedAppsAndMigrations:
    """Tests for get_changed_apps_and_migrations."""

    def test_extracts_app_and_migration(self):
        """Test parsing app labels and migration names from file paths."""
        changed_files = [
            "/project/myapp/migrations/0002_add_email.py",
            "/project/otherapp/migrations/0001_initial.py",
        ]

        with patch(
            "django_safe_migrations.diff.get_changed_migration_files",
            return_value=changed_files,
        ):
            result = get_changed_apps_and_migrations("main")

        assert ("myapp", "0002_add_email") in result
        assert ("otherapp", "0001_initial") in result

    def test_skips_init_files(self):
        """Test that __init__.py files are skipped."""
        changed_files = [
            "/project/myapp/migrations/__init__.py",
            "/project/myapp/migrations/0001_initial.py",
        ]

        with patch(
            "django_safe_migrations.diff.get_changed_migration_files",
            return_value=changed_files,
        ):
            result = get_changed_apps_and_migrations("main")

        assert len(result) == 1
        assert result[0] == ("myapp", "0001_initial")

    def test_empty_changed_files(self):
        """Test with no changed files."""
        with patch(
            "django_safe_migrations.diff.get_changed_migration_files",
            return_value=[],
        ):
            result = get_changed_apps_and_migrations("main")

        assert result == []

    def test_passes_base_ref(self):
        """Test that base_ref is forwarded to get_changed_migration_files."""
        with patch(
            "django_safe_migrations.diff.get_changed_migration_files",
            return_value=[],
        ) as mock_fn:
            get_changed_apps_and_migrations("feature-branch")

        mock_fn.assert_called_once_with("feature-branch")

    def test_multiple_migrations_same_app(self):
        """Test handling multiple migrations from the same app."""
        changed_files = [
            "/project/myapp/migrations/0001_initial.py",
            "/project/myapp/migrations/0002_add_field.py",
            "/project/myapp/migrations/0003_remove_field.py",
        ]

        with patch(
            "django_safe_migrations.diff.get_changed_migration_files",
            return_value=changed_files,
        ):
            result = get_changed_apps_and_migrations("main")

        assert len(result) == 3
        assert all(app == "myapp" for app, _ in result)
        migration_names = [name for _, name in result]
        assert "0001_initial" in migration_names
        assert "0002_add_field" in migration_names
        assert "0003_remove_field" in migration_names
