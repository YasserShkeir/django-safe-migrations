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

from django.apps import apps as django_apps

logger = logging.getLogger("django_safe_migrations")


class DiffError(Exception):
    """Raised when git diff fails (e.g. invalid branch/ref)."""

    pass


def _run_git_diff_names(diff_args: list[str]) -> list[str]:
    """Run ``git diff --name-only`` with *diff_args* and return migration files.

    Shared plumbing for working-tree diffs (``--diff``) and committed-range
    diffs (``--since-commit``). Filters the output to Python files under any
    ``migrations/`` directory that still exist on disk.

    Args:
        diff_args: Extra arguments passed to ``git diff`` after the standard
            ``--name-only --diff-filter=ACMR`` (e.g. ``["main"]`` or
            ``["abc123..HEAD"]``).

    Returns:
        List of absolute paths to changed migration files.

    Raises:
        DiffError: If an arg looks like a git option, or git fails / is absent.
    """
    # Reject args that could be interpreted as git options (argument injection,
    # e.g. ``--output=<file>`` which would make git write to an arbitrary path).
    # A leading dash is never valid in a branch/tag/commit or a ``A..B`` range.
    for arg in diff_args:
        if arg.startswith("-"):
            raise DiffError(f"Invalid git ref '{arg}': refs may not start with '-'.")
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "diff", "--name-only", "--diff-filter=ACMR", *diff_args],
            capture_output=True,
            text=True,
            check=True,
            cwd=_find_git_root(),
        )
    except subprocess.CalledProcessError as e:
        msg = f"Could not run git diff ({' '.join(diff_args)}): {e}"
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

    return changed


def get_changed_migration_files(base_ref: str = "main") -> list[str]:
    """Get migration files changed since *base_ref* (vs the working tree).

    Uses ``git diff --name-only`` to find Python files under any
    ``migrations/`` directory that have been added or modified relative to
    *base_ref*, including uncommitted working-tree changes.

    Args:
        base_ref: Git ref to diff against (branch, tag, or commit).

    Returns:
        List of absolute paths to changed migration files.

    Raises:
        DiffError: If the git ref does not exist or git command fails.
    """
    changed = _run_git_diff_names([base_ref])
    logger.debug("Found %d changed migration file(s) since %s", len(changed), base_ref)
    return changed


def get_committed_migration_files(since_commit: str) -> list[str]:
    """Get migration files committed since *since_commit* (excludes working tree).

    Unlike :func:`get_changed_migration_files`, this diffs the committed range
    ``<since_commit>..HEAD`` so that uncommitted edits are ignored. This suits
    incremental CI ("lint only what was committed since the last green build").

    Args:
        since_commit: Git commit/ref marking the lower bound (exclusive).

    Returns:
        List of absolute paths to migration files changed in the range.

    Raises:
        DiffError: If *since_commit* is empty/invalid or git command fails.
    """
    if not since_commit or not since_commit.strip():
        raise DiffError("--since-commit requires a non-empty commit/ref.")
    changed = _run_git_diff_names([f"{since_commit}..HEAD"])
    logger.debug(
        "Found %d migration file(s) committed since %s", len(changed), since_commit
    )
    return changed


def _files_to_app_migrations(files: list[str]) -> list[tuple[str, str]]:
    """Map changed migration file paths to (app_label, migration_name) pairs.

    The app label is resolved via Django's app registry so that apps whose
    ``AppConfig.label`` differs from their package directory name are handled
    correctly.

    Args:
        files: Absolute paths to changed migration files.

    Returns:
        List of (app_label, migration_name) tuples (``__init__`` skipped).
    """
    result: list[tuple[str, str]] = []

    # Map resolved app package paths to their registered labels once. Using the
    # registry label (rather than assuming directory name == label) handles
    # custom ``AppConfig.label`` values; resolving paths makes the lookup robust
    # to symlinks / non-normalized roots, and building the dict once keeps this
    # O(files) instead of O(files x app_configs).
    path_to_label = {
        Path(app_config.path).resolve(): app_config.label
        for app_config in django_apps.get_app_configs()
    }

    for filepath in files:
        path = Path(filepath)
        # Expected: .../app_name/migrations/0001_initial.py
        migration_name = path.stem  # e.g. "0001_initial"
        if migration_name == "__init__":
            continue

        migrations_dir = path.parent  # .../app_name/migrations/
        app_dir = migrations_dir.parent  # .../app_name/

        app_label = path_to_label.get(app_dir.resolve(), app_dir.name)

        result.append((app_label, migration_name))

    logger.debug("Changed migrations: %s", result)
    return result


def get_changed_apps_and_migrations(
    base_ref: str = "main",
) -> list[tuple[str, str]]:
    """Get (app_label, migration_name) pairs for migrations changed vs *base_ref*.

    Includes uncommitted working-tree changes (mirrors ``--diff``).

    Args:
        base_ref: Git ref to diff against.

    Returns:
        List of (app_label, migration_name) tuples.
    """
    return _files_to_app_migrations(get_changed_migration_files(base_ref))


def get_committed_apps_and_migrations(
    since_commit: str,
) -> list[tuple[str, str]]:
    """Get (app_label, migration_name) pairs for migrations committed since a ref.

    Diffs the committed range ``<since_commit>..HEAD``; uncommitted edits are
    ignored (mirrors ``--since-commit``).

    Args:
        since_commit: Git commit/ref marking the lower bound (exclusive).

    Returns:
        List of (app_label, migration_name) tuples.
    """
    return _files_to_app_migrations(get_committed_migration_files(since_commit))


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
