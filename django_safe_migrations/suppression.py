"""Inline suppression comment parsing for django-safe-migrations.

This module provides functionality to parse inline suppression comments
in migration files, allowing developers to suppress specific warnings
on a per-operation basis.

Supported formats:
    # safe-migrations: ignore SM001
    # safe-migrations: ignore SM001, SM002
    # safe-migrations: ignore SM001 -- intentional cleanup
    # safe-migrations: ignore all
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger("django_safe_migrations")

if TYPE_CHECKING:
    from django.db.migrations import Migration

# Pattern to match suppression comments
# Matches: # safe-migrations: ignore SM001, SM002 -- optional reason
SUPPRESSION_PATTERN = re.compile(
    r"#\s*safe-migrations:\s*ignore\s+"
    r"(?P<rules>all|SM\d{3}(?:\s*,\s*SM\d{3})*)"
    r"(?:\s*--\s*(?P<reason>.*))?",
    re.IGNORECASE,
)


@dataclass
class Suppression:
    """Represents a suppression comment.

    Attributes:
        rules: Set of rule IDs to suppress, or {"all"} for all rules.
        reason: Optional reason for the suppression.
        line_number: Line number where the suppression was found.
    """

    rules: set[str]
    reason: Optional[str]
    line_number: int

    def suppresses(self, rule_id: str) -> bool:
        """Check if this suppression applies to a rule.

        Args:
            rule_id: The rule ID to check.

        Returns:
            True if this suppression covers the rule.
        """
        return "all" in self.rules or rule_id.upper() in self.rules


def parse_suppression_comment(line: str, line_number: int) -> Optional[Suppression]:
    """Parse a single line for a suppression comment.

    Args:
        line: The line of code to parse.
        line_number: The line number in the file.

    Returns:
        A Suppression object if found, None otherwise.
    """
    match = SUPPRESSION_PATTERN.search(line)
    if not match:
        return None

    rules_str = match.group("rules")
    reason = match.group("reason")

    if rules_str.lower() == "all":
        rules = {"all"}
    else:
        # Parse comma-separated rule IDs
        rules = {r.strip().upper() for r in rules_str.split(",")}

        # Validate rule IDs against known rules
        from django_safe_migrations.rules import ALL_RULES

        known_ids = {cls.rule_id for cls in ALL_RULES if hasattr(cls, "rule_id")}
        unknown = rules - known_ids
        if unknown:
            logger.warning(
                "Line %d: suppression references unknown rule(s): %s",
                line_number,
                ", ".join(sorted(unknown)),
            )

    return Suppression(
        rules=rules,
        reason=reason.strip() if reason else None,
        line_number=line_number,
    )


def get_suppressions_for_migration(migration: Migration) -> dict[int, Suppression]:
    """Get all suppression comments from a migration file.

    Args:
        migration: A Django migration instance.

    Returns:
        A dictionary mapping line numbers to Suppression objects.
    """
    from django_safe_migrations.utils import get_migration_file_path

    file_path = get_migration_file_path(migration)
    if not file_path or not os.path.exists(file_path):
        return {}

    return get_suppressions_from_file(file_path)


def get_suppressions_from_file(file_path: str) -> dict[int, Suppression]:
    """Get all suppression comments from a file.

    Args:
        file_path: Path to the migration file.

    Returns:
        A dictionary mapping line numbers to Suppression objects.
    """
    suppressions: dict[int, Suppression] = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                suppression = parse_suppression_comment(line, line_number)
                if suppression:
                    suppressions[line_number] = suppression
    except OSError:
        pass

    return suppressions


def is_operation_suppressed(
    file_path: str,
    operation_line: int,
    rule_id: str,
    suppressions: Optional[dict[int, Suppression]] = None,
) -> bool:
    """Check if an operation is suppressed for a specific rule.

    Suppression comments apply to the operation immediately following them.
    A suppression comment can be on the line immediately before the operation,
    or on the same line as the operation.

    Args:
        file_path: Path to the migration file.
        operation_line: Line number of the operation.
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions (optional, for performance).

    Returns:
        True if the operation is suppressed for this rule.
    """
    if suppressions is None:
        suppressions = get_suppressions_from_file(file_path)

    # Check for suppression on the same line
    if operation_line in suppressions:
        if suppressions[operation_line].suppresses(rule_id):
            return True

    # Check for suppression on the line immediately before
    prev_line = operation_line - 1
    if prev_line in suppressions:
        if suppressions[prev_line].suppresses(rule_id):
            return True

    # Check for suppression two lines before (common pattern with blank line)
    prev_prev_line = operation_line - 2
    if prev_prev_line in suppressions:
        if suppressions[prev_prev_line].suppresses(rule_id):
            return True

    return False


def get_suppression_reason(
    file_path: str,
    operation_line: int,
    rule_id: str,
    suppressions: Optional[dict[int, Suppression]] = None,
) -> Optional[str]:
    """Get the reason for a suppression, if any.

    Args:
        file_path: Path to the migration file.
        operation_line: Line number of the operation.
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions (optional, for performance).

    Returns:
        The suppression reason if found, None otherwise.
    """
    if suppressions is None:
        suppressions = get_suppressions_from_file(file_path)

    for offset in [0, -1, -2]:
        check_line = operation_line + offset
        if check_line in suppressions:
            sup = suppressions[check_line]
            if sup.suppresses(rule_id):
                return sup.reason

    return None
