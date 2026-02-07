"""Tests for watch mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from django_safe_migrations.watch import MigrationFileHandler, has_watchdog


class TestHasWatchdog:
    """Tests for has_watchdog."""

    def test_returns_bool(self):
        """Test that has_watchdog returns a boolean."""
        result = has_watchdog()
        assert isinstance(result, bool)

    def test_returns_true_when_watchdog_installed(self):
        """Test that has_watchdog returns True when watchdog is available."""
        with patch("django_safe_migrations.watch._HAS_WATCHDOG", True):
            assert has_watchdog() is True

    def test_returns_false_when_watchdog_missing(self):
        """Test that has_watchdog returns False when watchdog is not available."""
        with patch("django_safe_migrations.watch._HAS_WATCHDOG", False):
            assert has_watchdog() is False


class TestMigrationFileHandler:
    """Tests for MigrationFileHandler."""

    def test_callback_on_migration_file_modified(self):
        """Test that the callback is invoked when a migration .py file is modified."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/migrations/0002_add_field.py"

        handler.on_modified(event)

        callback.assert_called_once()

    def test_no_callback_for_directory(self):
        """Test that the callback is not invoked for directory events."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = True
        event.src_path = "/project/myapp/migrations/"

        handler.on_modified(event)

        callback.assert_not_called()

    def test_no_callback_for_non_python_file(self):
        """Test that the callback is not invoked for non-Python files."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/migrations/README.md"

        handler.on_modified(event)

        callback.assert_not_called()

    def test_no_callback_for_non_migration_python_file(self):
        """Test that the callback is not invoked for Python files outside migrations."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/models.py"

        handler.on_modified(event)

        callback.assert_not_called()

    def test_callback_on_migration_file_created(self):
        """Test that the callback is invoked when a migration file is created."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/migrations/0003_new.py"

        handler.on_created(event)

        callback.assert_called_once()

    def test_no_callback_for_non_migration_created(self):
        """Test that on_created does not trigger for non-migration files."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/views.py"

        handler.on_created(event)

        callback.assert_not_called()

    def test_callback_for_nested_migration_path(self):
        """Test that deeply nested migration paths still trigger the callback."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/deep/nested/path/app/migrations/0001_initial.py"

        handler.on_modified(event)

        callback.assert_called_once()

    def test_callback_for_init_py_in_migrations(self):
        """Test that __init__.py inside migrations triggers the callback."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/myapp/migrations/__init__.py"

        handler.on_modified(event)

        callback.assert_called_once()

    def test_stores_callback(self):
        """Test that the handler stores the callback reference."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        assert handler.callback is callback

    def test_multiple_events_trigger_multiple_callbacks(self):
        """Test that multiple file events each trigger the callback."""
        callback = MagicMock()
        handler = MigrationFileHandler(callback=callback)

        for i in range(3):
            event = MagicMock()
            event.is_directory = False
            event.src_path = f"/project/myapp/migrations/000{i}_test.py"
            handler.on_modified(event)

        assert callback.call_count == 3


class TestWatchMigrations:
    """Tests for watch_migrations function."""

    def test_raises_import_error_without_watchdog(self):
        """Test that watch_migrations raises ImportError when watchdog is missing."""
        from django_safe_migrations.watch import watch_migrations

        with patch("django_safe_migrations.watch._HAS_WATCHDOG", False):
            with pytest.raises(ImportError, match="watchdog is required"):
                watch_migrations()
