"""GitLab Code Quality reporter.

Outputs issues in GitLab Code Quality JSON format for integration
with GitLab CI merge request widgets.

See: https://docs.gitlab.com/ee/ci/testing/code_quality.html
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import TYPE_CHECKING, Any, TextIO

from django_safe_migrations.reporters.base import BaseReporter

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


# Map our severity levels to GitLab Code Quality severity
_SEVERITY_MAP = {
    "error": "critical",
    "warning": "major",
    "info": "minor",
}


class GitLabReporter(BaseReporter):
    """Reporter that outputs issues in GitLab Code Quality JSON format."""

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize the GitLab reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
        """
        super().__init__(stream or sys.stdout)

    def report(self, issues: list[Issue]) -> str:
        """Generate a GitLab Code Quality JSON report.

        Args:
            issues: List of issues to report.

        Returns:
            The JSON report as a string.
        """
        entries: list[dict[str, Any]] = []

        for issue in issues:
            entry = self._issue_to_entry(issue)
            entries.append(entry)

        output = json.dumps(entries, indent=2)
        self.write(output)
        return output

    @staticmethod
    def _issue_to_entry(issue: Issue) -> dict[str, Any]:
        """Convert an Issue to a GitLab Code Quality entry.

        Args:
            issue: The issue to convert.

        Returns:
            A dictionary in GitLab Code Quality format.
        """
        # Build a stable fingerprint from the issue identity
        fingerprint_source = (
            f"{issue.rule_id}:{issue.app_label}:"
            f"{issue.migration_name}:{issue.operation}"
        )
        fingerprint = hashlib.md5(  # noqa: S324  # nosec B324
            fingerprint_source.encode()
        ).hexdigest()

        severity = _SEVERITY_MAP.get(issue.severity.value, "info")

        entry: dict[str, Any] = {
            "type": "issue",
            "check_name": issue.rule_id,
            "description": issue.message,
            "categories": ["Migration Safety"],
            "severity": severity,
            "fingerprint": fingerprint,
            "location": {
                "path": issue.file_path or "unknown",
                "lines": {
                    "begin": issue.line_number or 1,
                },
            },
        }

        return entry
