"""Watch mode for continuous migration checking.

Requires the ``watchdog`` package (optional dependency)::

    pip install django-safe-migrations[watch]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from watchdog.events import FileSystemEvent

_HAS_WATCHDOG = False
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    _HAS_WATCHDOG = True
except ImportError:
    # Provide stubs so the module can be imported without watchdog
    class FileSystemEventHandler:  # type: ignore[no-redef]
        """Stub for missing watchdog."""

        pass

    Observer = None


def has_watchdog() -> bool:
    """Return True if watchdog is installed."""
    return _HAS_WATCHDOG


class MigrationFileHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Watches for changes to migration files and triggers a callback."""

    def __init__(self, callback: Callable[[], None]) -> None:  # noqa: D107
        super().__init__()
        self.callback = callback

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events.

        Args:
            event: The file system event.
        """
        if event.is_directory:
            return
        if str(event.src_path).endswith(".py") and "/migrations/" in str(
            event.src_path
        ):
            print(f"\nChange detected: {event.src_path}", file=sys.stderr)
            self.callback()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events.

        Args:
            event: The file system event.
        """
        self.on_modified(event)


def watch_migrations(
    paths: list[str] | None = None,
    callback: Callable[[], None] | None = None,
) -> None:
    """Watch migration directories for changes and re-run analysis.

    Args:
        paths: List of directory paths to watch. If None, discovers
               migration directories from installed Django apps.
        callback: Function to call when changes are detected.
                  If None, a default callback is used.

    Raises:
        ImportError: If watchdog is not installed.
    """
    if not _HAS_WATCHDOG:
        raise ImportError(
            "watchdog is required for watch mode. "
            "Install it with: pip install django-safe-migrations[watch]"
        )

    if paths is None:
        paths = _discover_migration_paths()

    if callback is None:
        callback = _default_analysis_callback

    observer = Observer()
    handler = MigrationFileHandler(callback)

    for path in paths:
        if Path(path).exists():
            observer.schedule(handler, path, recursive=True)
            print(f"Watching: {path}", file=sys.stderr)

    if not observer._watches:
        print("No migration directories found to watch.", file=sys.stderr)
        return

    print("Press Ctrl+C to stop watching.\n", file=sys.stderr)

    # Run initial analysis
    callback()

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.", file=sys.stderr)

    observer.join()


def _discover_migration_paths() -> list[str]:
    """Discover migration directories from installed Django apps.

    Returns:
        List of migration directory paths.
    """
    from django.apps import apps

    paths = []
    for app_config in apps.get_app_configs():
        migrations_dir = Path(app_config.path) / "migrations"
        if migrations_dir.exists():
            paths.append(str(migrations_dir))
    return paths


def _default_analysis_callback() -> None:
    """Run migration analysis and print results."""
    from django_safe_migrations.analyzer import MigrationAnalyzer
    from django_safe_migrations.reporters import get_reporter

    try:
        analyzer = MigrationAnalyzer()
        issues = analyzer.analyze_all()
        reporter = get_reporter("console", stream=sys.stdout)
        reporter.report(issues)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
