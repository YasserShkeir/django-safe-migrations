"""Baseline support for suppressing known issues.

A baseline file records existing issues so they can be excluded from
future runs.  This allows teams to adopt ``django-safe-migrations``
incrementally without being overwhelmed by existing violations.

Usage::

    # Generate a baseline from current issues
    python manage.py check_migrations --generate-baseline .migration-baseline.json

    # Run checks excluding baselined issues
    python manage.py check_migrations --baseline .migration-baseline.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue

logger = logging.getLogger("django_safe_migrations")


def generate_baseline(issues: list[Issue], path: str) -> int:
    """Generate a baseline file from current issues.

    The baseline records each issue by its rule_id, app_label,
    migration_name, and operation so it can be matched in future runs.

    Args:
        issues: Current list of issues.
        path: File path to write the baseline to.

    Returns:
        The number of issues baselined.
    """
    entries: list[dict[str, Any]] = []
    for issue in issues:
        entries.append(
            {
                "rule_id": issue.rule_id,
                "app_label": issue.app_label,
                "migration_name": issue.migration_name,
                "operation": issue.operation,
            }
        )

    data = {
        "version": 1,
        "count": len(entries),
        "issues": entries,
    }

    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("Generated baseline with %d issues at %s", len(entries), path)
    return len(entries)


def load_baseline(path: str) -> list[dict[str, Any]]:
    """Load a baseline file.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        List of baseline issue entries.

    Raises:
        FileNotFoundError: If the baseline file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)

    version = data.get("version", 1)
    if version != 1:
        logger.warning(
            "Unknown baseline version %s, attempting to load anyway", version
        )

    entries: list[dict[str, Any]] = data.get("issues", [])
    logger.debug("Loaded baseline with %d issues from %s", len(entries), path)
    return entries


def filter_baselined_issues(
    issues: list[Issue],
    baseline: list[dict[str, Any]],
) -> list[Issue]:
    """Remove issues that are present in the baseline.

    Matching is done by (rule_id, app_label, migration_name, operation).

    Args:
        issues: Current list of issues.
        baseline: Baseline entries to exclude.

    Returns:
        Filtered list of issues not in the baseline.
    """
    baseline_keys = {
        (
            entry.get("rule_id"),
            entry.get("app_label"),
            entry.get("migration_name"),
            entry.get("operation"),
        )
        for entry in baseline
    }

    filtered = []
    suppressed = 0
    for issue in issues:
        key = (issue.rule_id, issue.app_label, issue.migration_name, issue.operation)
        if key in baseline_keys:
            suppressed += 1
        else:
            filtered.append(issue)

    if suppressed:
        logger.info(
            "Baseline suppressed %d issue(s), %d remaining",
            suppressed,
            len(filtered),
        )

    return filtered
