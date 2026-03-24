"""Diff mode for checking only changed migration files.

Uses ``git diff`` to detect migration files that have changed since
a given base branch, then only analyses those migrations.

Usage::

    python manage.py check_migrations --diff
    python manage.py check_migrations --diff main
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404
from pathlib import Path

logger = logging.getLogger("django_safe_migrations")


class DiffError(Exception):
    """Raised when git diff fails (e.g. invalid branch/ref)."""

    pass


def get_changed_migration_files(base_ref: str = "main") -> list[str]:
    """Get migration files changed since *base_ref*.

    Uses ``git diff --name-only`` to find Python files under any
    ``migrations/`` directory that have been added or modified.

    Args:
        base_ref: Git ref to diff against (branch, tag, or commit).

    Returns:
        List of absolute paths to changed migration files.

    Raises:
        DiffError: If the git ref does not exist or git command fails.
    """
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base_ref],
            capture_output=True,
            text=True,
            check=True,
            cwd=_find_git_root(),
        )
    except subprocess.CalledProcessError as e:
        msg = f"Could not run git diff against '{base_ref}': {e}"
        if e.stderr:
            msg += f"\ngit stderr: {e.stderr.strip()}"
        logger.error(msg)
        raise DiffError(msg) from e
    except FileNotFoundError as e:
        msg = f"git is not installed or not found: {e}"
        logger.error(msg)
        raise DiffError(msg) from e

    git_root = _find_git_root()
    changed: list[str] = []

    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Only migration Python files
        if "/migrations/" in line and line.endswith(".py"):
            abs_path = os.path.join(git_root, line)
            if os.path.exists(abs_path):
                changed.append(abs_path)

    logger.debug("Found %d changed migration file(s) since %s", len(changed), base_ref)
    return changed


def get_changed_apps_and_migrations(
    base_ref: str = "main",
) -> list[tuple[str, str]]:
    """Get (app_label, migration_name) pairs for changed migrations.

    Parses the file paths to extract app labels and migration names.

    Args:
        base_ref: Git ref to diff against.

    Returns:
        List of (app_label, migration_name) tuples.
    """
    files = get_changed_migration_files(base_ref)
    result: list[tuple[str, str]] = []

    for filepath in files:
        path = Path(filepath)
        # Expected: .../app_name/migrations/0001_initial.py
        migration_name = path.stem  # e.g. "0001_initial"
        if migration_name == "__init__":
            continue

        migrations_dir = path.parent  # .../app_name/migrations/
        app_dir = migrations_dir.parent  # .../app_name/

        # The app label is typically the directory name
        app_label = app_dir.name

        result.append((app_label, migration_name))

    logger.debug("Changed migrations: %s", result)
    return result


def _find_git_root() -> str:
    """Find the git repository root directory.

    Returns:
        Absolute path to the git root, or cwd if not in a git repo.
    """
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()
