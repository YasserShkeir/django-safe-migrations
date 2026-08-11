"""Inline suppression comment parsing for django-safe-migrations.

This module provides functionality to parse inline suppression comments
in migration files, allowing developers to suppress specific warnings
on a per-operation or whole-migration basis.

Supported formats:
    # safe-migrations: ignore SM001
    # safe-migrations: ignore SM001, SM002
    # safe-migrations: ignore SM001 -- intentional cleanup
    # safe-migrations: ignore all
    # safe-migrations: ignore-migration SM038 -- schema/data mix reviewed

Where a directive counts
------------------------
A directive is honoured **only** when it is a real Python comment and the
directive starts at the very beginning of that comment. Concretely:

- Comments are located with :mod:`tokenize`, so the phrase is ignored inside
  docstrings, ``RunSQL`` string literals and any other string.
- The pattern is matched *anchored* to the start of the comment token, so a
  commented-out directive (``# # safe-migrations: ...``) or the phrase quoted
  in prose (``# never write `# safe-migrations: ignore all` here``) does not
  fire.

This matters because ``ignore-migration`` silences a rule for the whole file:
an accidental match anywhere would turn the entire migration into a blind
spot. When a file cannot be tokenised (syntax error), parsing degrades to an
anchored raw-line scan of the untokenisable tail rather than crashing.

A rule covered by a directive is **skipped, not run-and-filtered**: whatever
the rule would have done (including raising) must not affect a migration the
author already silenced. Each skipped check is recorded as a
:class:`SuppressionRecord` by the analyzer and reported, so a clean run never
hides a skipped check.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tokenize
from dataclasses import dataclass
from enum import Enum, unique
from typing import TYPE_CHECKING, Iterable, Optional

logger = logging.getLogger("django_safe_migrations")

if TYPE_CHECKING:
    from django.db.migrations import Migration

# Pattern to match suppression comments.
#
# Matched with ``.match()`` against an isolated comment token (text starting at
# the comment's own ``#``) -- never ``.search()`` against a raw source line.
# The leading ``#`` therefore anchors the directive to the start of the
# comment, which is what rejects ``# # safe-migrations: ...`` and prose
# mentions.
SUPPRESSION_PATTERN = re.compile(
    r"#\s*safe-migrations:\s*"
    r"(?P<action>ignore-migration|ignore)\s+"
    r"(?P<rules>all|SM\d{3}(?:\s*,\s*SM\d{3})*)"
    r"(?:\s*--\s*(?P<reason>.*))?",
    re.IGNORECASE,
)

# Cheap pre-filter for :func:`_parse_source`. Every directive SUPPRESSION_PATTERN
# can match contains this literal, so a file without it cannot hold one and does
# not need tokenising -- which is the expensive part of parsing, and is otherwise
# paid for every migration file on every run.
DIRECTIVE_HINT = re.compile(r"safe-migrations:", re.IGNORECASE)


@unique
class SuppressionScope(Enum):
    """Scope where a suppression applies."""

    OPERATION = "operation"
    MIGRATION = "migration"


@dataclass
class Suppression:
    """Represents a suppression comment.

    Attributes:
        rules: Set of rule IDs to suppress, or {"all"} for all rules.
        reason: Optional reason for the suppression.
        line_number: Line number where the suppression was found.
        scope: Suppression scope.
    """

    rules: set[str]
    reason: Optional[str]
    line_number: int
    scope: SuppressionScope = SuppressionScope.OPERATION

    def suppresses(self, rule_id: str) -> bool:
        """Check if this suppression applies to a rule.

        Args:
            rule_id: The rule ID to check.

        Returns:
            True if this suppression covers the rule.
        """
        return "all" in self.rules or rule_id.upper() in self.rules

    def report_rule_id(self, rule_id: str) -> str:
        """Return the label to report for a check this directive silenced.

        A blanket ``all`` directive covers every rule in the suite. Since a
        suppressed rule is never run, reporting it per rule would emit one
        line for each rule in the suite; ``all`` says the same thing once.

        Args:
            rule_id: The rule that was not run.

        Returns:
            ``"all"`` for a blanket directive, else ``rule_id``.
        """
        return "all" if "all" in self.rules else rule_id


@dataclass
class SuppressionRecord:
    """One check that a suppression comment silenced.

    A suppressed rule is skipped, not run-and-filtered, so this names the
    check that did not run rather than a confirmed finding. A blanket
    directive is recorded once as ``all`` (see
    :meth:`Suppression.report_rule_id`) instead of once per rule.

    Attributes:
        rule_id: The rule that was not run, or ``"all"``.
        scope: Whether the directive was operation- or migration-scoped.
        line_number: Line of the suppression comment itself.
        reason: The ``--`` reason from the comment, if any.
        file_path: Migration file the suppression lives in.
        app_label: App the migration belongs to.
        migration_name: Migration the suppression applies to.
    """

    rule_id: str
    scope: SuppressionScope
    line_number: int
    reason: Optional[str] = None
    file_path: Optional[str] = None
    app_label: Optional[str] = None
    migration_name: Optional[str] = None

    def _key(self) -> tuple[str, str, int, str]:
        """Return the identity used to collapse duplicate records."""
        return (
            self.file_path or "",
            self.rule_id,
            self.line_number,
            self.scope.value,
        )

    def format(self) -> str:
        """Return a single human-readable audit line for this record."""
        location = self.file_path or ""
        if self.app_label and self.migration_name:
            label = f"{self.app_label}/{self.migration_name}"
            location = f"{location} ({label})" if location else label
        parts = [
            (
                f"{location}:{self.line_number}"
                if location
                else f"line {self.line_number}"
            ),
            self.rule_id,
            f"[{self.scope.value}]",
        ]
        line = " ".join(parts)
        if self.reason:
            line = f"{line} -- {self.reason}"
        return line


def format_suppression_report(records: Iterable[SuppressionRecord]) -> str:
    """Render suppression records as an auditable, deterministic block.

    Args:
        records: Records collected during analysis.

    Returns:
        A multi-line string, or ``""`` when nothing was suppressed.
    """
    unique_records: dict[tuple[str, str, int, str], SuppressionRecord] = {}
    for record in records:
        unique_records.setdefault(record._key(), record)

    if not unique_records:
        return ""

    ordered = [unique_records[key] for key in sorted(unique_records)]
    lines = [f"Suppressed {len(ordered)} check(s) via inline comments:"]
    lines.extend(f"  {record.format()}" for record in ordered)
    return "\n".join(lines)


def _parse_comment_token(comment: str, line_number: int) -> Optional[Suppression]:
    """Parse an isolated comment token for a suppression directive.

    Args:
        comment: The comment text, starting at its own ``#``.
        line_number: The line number in the file.

    Returns:
        A Suppression object if the comment *is* a directive, None otherwise.
    """
    # Anchored: the directive must be the whole comment, not something the
    # comment merely mentions or has commented out.
    match = SUPPRESSION_PATTERN.match(comment.strip())
    if not match:
        return None

    rules_str = match.group("rules")
    reason = match.group("reason")
    action = match.group("action").lower()
    scope = (
        SuppressionScope.MIGRATION
        if action == "ignore-migration"
        else SuppressionScope.OPERATION
    )

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
        scope=scope,
    )


def parse_suppression_comment(line: str, line_number: int) -> Optional[Suppression]:
    """Parse a single raw source line for a suppression comment.

    The directive must begin at the start of the line's comment, so a
    commented-out directive or a directive quoted inside prose is not honoured.
    This is the string-unaware fallback; :func:`get_suppressions_from_file`
    tokenises instead, which additionally ignores directives inside string
    literals.

    Args:
        line: The line of code to parse.
        line_number: The line number in the file.

    Returns:
        A Suppression object if found, None otherwise.
    """
    comment_start = line.find("#")
    if comment_start == -1:
        return None
    return _parse_comment_token(line[comment_start:], line_number)


def _tokenize_comments(source: str) -> tuple[dict[int, str], Optional[int]]:
    """Extract real comment tokens from Python source.

    Args:
        source: The file's source text.

    Returns:
        A ``(comments, tokenized_through)`` pair. ``comments`` maps line
        numbers to comment token text. ``tokenized_through`` is ``None`` when
        the whole file tokenised cleanly, otherwise the last line the tokenizer
        managed to reach (lines past it need the raw-line fallback).
    """
    comments: dict[int, str] = {}
    last_line = 0
    try:
        readline = io.StringIO(source).readline
        for token in tokenize.generate_tokens(readline):
            last_line = max(last_line, token.end[0])
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError) as exc:
        # A migration that does not tokenise is broken anyway; degrade to the
        # anchored line scan for the tail rather than losing every directive.
        logger.debug("Tokenizing failed (%s); falling back to line scan", exc)
        return comments, last_line
    return comments, None


def _parse_source(source: str) -> dict[int, Suppression]:
    """Collect suppressions from source text.

    Args:
        source: The file's source text.

    Returns:
        A dictionary mapping line numbers to Suppression objects.
    """
    # Skip the tokenizer entirely when the file cannot contain a directive.
    # Purely a shortcut: the literal is a necessary part of every match, so
    # this can only skip files that would have yielded nothing.
    if not DIRECTIVE_HINT.search(source):
        return {}

    suppressions: dict[int, Suppression] = {}

    comments, tokenized_through = _tokenize_comments(source)
    for line_number, comment in comments.items():
        suppression = _parse_comment_token(comment, line_number)
        if suppression:
            suppressions[line_number] = suppression

    if tokenized_through is not None:
        for line_number, line in enumerate(source.splitlines(), start=1):
            if line_number <= tokenized_through:
                continue
            suppression = parse_suppression_comment(line, line_number)
            if suppression:
                suppressions[line_number] = suppression

    return suppressions


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
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return {}

    return _parse_source(source)


def find_operation_suppression(
    file_path: Optional[str],
    operation_line: Optional[int],
    rule_id: str,
    suppressions: Optional[dict[int, Suppression]] = None,
) -> Optional[Suppression]:
    """Return the operation-scoped suppression covering a rule, if any.

    Suppression comments apply to the operation immediately following them.
    A suppression comment can be on the line immediately before the operation,
    on the line two before (the common blank-line pattern), or on the same
    line as the operation.

    Args:
        file_path: Path to the migration file.
        operation_line: Line number of the operation.
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions (optional, for performance).

    Returns:
        The matching Suppression, or None.
    """
    if operation_line is None:
        return None
    if suppressions is None:
        if not file_path:
            return None
        suppressions = get_suppressions_from_file(file_path)

    for offset in (0, -1, -2):
        candidate = suppressions.get(operation_line + offset)
        if (
            candidate is not None
            and candidate.scope is SuppressionScope.OPERATION
            and candidate.suppresses(rule_id)
        ):
            return candidate

    return None


def is_operation_suppressed(
    file_path: str,
    operation_line: int,
    rule_id: str,
    suppressions: Optional[dict[int, Suppression]] = None,
) -> bool:
    """Check if an operation is suppressed for a specific rule.

    Args:
        file_path: Path to the migration file.
        operation_line: Line number of the operation.
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions (optional, for performance).

    Returns:
        True if the operation is suppressed for this rule.
    """
    return (
        find_operation_suppression(file_path, operation_line, rule_id, suppressions)
        is not None
    )


def find_migration_suppression(
    rule_id: str,
    suppressions: dict[int, Suppression],
) -> Optional[Suppression]:
    """Return the migration-scoped suppression covering a rule, if any.

    Args:
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions for the migration file.

    Returns:
        The matching Suppression, or None.
    """
    for line_number in sorted(suppressions):
        candidate = suppressions[line_number]
        if candidate.scope is SuppressionScope.MIGRATION and candidate.suppresses(
            rule_id
        ):
            return candidate
    return None


def is_migration_suppressed(
    rule_id: str,
    suppressions: dict[int, Suppression],
) -> bool:
    """Check if a migration is suppressed for a specific rule.

    Args:
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions for the migration file.

    Returns:
        True if any migration-level suppression covers the rule.
    """
    return find_migration_suppression(rule_id, suppressions) is not None


def find_suppression(
    rule_id: str,
    suppressions: dict[int, Suppression],
    file_path: Optional[str] = None,
    operation_line: Optional[int] = None,
) -> Optional[Suppression]:
    """Return whichever suppression silences ``rule_id`` here, if any.

    Migration-scoped directives win because they cover the whole file; an
    operation-scoped directive only applies next to its operation.

    Args:
        rule_id: The rule ID to check.
        suppressions: Pre-parsed suppressions for the migration file.
        file_path: Path to the migration file.
        operation_line: Line number of the operation, if operation-scoped
            suppression should also be considered.

    Returns:
        The matching Suppression, or None.
    """
    migration_level = find_migration_suppression(rule_id, suppressions)
    if migration_level is not None:
        return migration_level
    return find_operation_suppression(file_path, operation_line, rule_id, suppressions)


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
    suppression = find_operation_suppression(
        file_path, operation_line, rule_id, suppressions
    )
    return suppression.reason if suppression else None
