"""GitHub pull-request comment reporter.

Emits a Markdown summary suitable for posting as a single pull-request comment,
grouped by migration file. Unlike the ``github`` reporter (which emits
``::error file=...::`` workflow commands that become inline annotations), this
reporter produces a human-readable comment body that a CI step posts with, e.g.::

    python manage.py check_migrations --format=github-pr > comment.md
    gh pr comment "$PR_NUMBER" --body-file comment.md

It performs no network I/O and needs no credentials — keeping it pure and
testable; posting is left to the CI step.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from django_safe_migrations.reporters.base import BaseReporter

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue

_TITLE = "Django Safe Migrations"
_FOOTER = (
    "<sub>Reported by "
    '<a href="https://github.com/YasserShkeir/django-safe-migrations">'
    "django-safe-migrations</a></sub>"
)
# Severity sort order (errors first) for stable, useful grouping.
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _escape_cell(text: str) -> str:
    """Make *text* safe to drop into a Markdown table cell."""
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


class GitHubPRReporter(BaseReporter):
    """Reporter that outputs a Markdown PR-comment body."""

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize the GitHub PR-comment reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
        """
        super().__init__(stream or sys.stdout)

    def report(self, issues: list[Issue]) -> str:
        """Generate a Markdown PR-comment report.

        Args:
            issues: List of issues to report.

        Returns:
            The Markdown report as a string.
        """
        if not issues:
            output = (
                f"## {_TITLE}\n\n"
                "No migration safety issues found.\n\n"
                f"{_FOOTER}\n"
            )
            self.write(output)
            return output

        errors = sum(1 for i in issues if i.severity.value == "error")
        warnings = sum(1 for i in issues if i.severity.value == "warning")
        infos = sum(1 for i in issues if i.severity.value == "info")

        # Group issues by migration file (preserving a stable order).
        by_file: dict[str, list[Issue]] = {}
        for issue in issues:
            key = issue.file_path or "(unknown migration)"
            by_file.setdefault(key, []).append(issue)

        lines: list[str] = [f"## {_TITLE}", ""]
        lines.append(self._summary_line(len(issues), errors, warnings, infos))
        lines.append("")

        for file_path in sorted(by_file):
            file_issues = sorted(
                by_file[file_path],
                key=lambda i: (
                    _SEVERITY_ORDER.get(i.severity.value, 9),
                    i.line_number or 0,
                    i.rule_id,
                ),
            )
            lines.append(f"### `{file_path}`")
            lines.append("")
            lines.append("| Severity | Rule | Line | Message |")
            lines.append("| --- | --- | --- | --- |")
            for issue in file_issues:
                line_no = str(issue.line_number) if issue.line_number else "—"
                lines.append(
                    f"| {issue.severity.value.upper()} "
                    f"| {issue.rule_id} "
                    f"| {line_no} "
                    f"| {_escape_cell(issue.message)} |"
                )
            lines.append("")

        lines.append(_FOOTER)
        output = "\n".join(lines) + "\n"
        self.write(output)
        return output

    @staticmethod
    def _summary_line(total: int, errors: int, warnings: int, infos: int) -> str:
        """Build the one-line summary of issue counts."""
        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        if infos:
            parts.append(f"{infos} info")
        breakdown = ", ".join(parts)
        noun = "issue" if total == 1 else "issues"
        return f"Found **{total} {noun}** — {breakdown}."
