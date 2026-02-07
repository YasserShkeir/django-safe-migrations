"""GitHub Actions reporter with workflow annotations."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from django_safe_migrations.reporters.base import BaseReporter
from django_safe_migrations.rules.base import Severity

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


class GitHubReporter(BaseReporter):
    """Reporter that outputs GitHub Actions workflow commands.

    This reporter uses GitHub's workflow commands to create annotations
    that appear directly in the PR diff and on the Actions summary.

    See:
    https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions
    """

    SEVERITY_COMMANDS = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "notice",
    }

    def __init__(self, stream: TextIO | None = None):
        """Initialize the GitHub reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
        """
        super().__init__(stream or sys.stdout)

    def _format_annotation(self, issue: Issue) -> str:
        """Format an issue as a GitHub workflow command.

        Args:
            issue: The issue to format.

        Returns:
            GitHub workflow command string.
        """
        command = self.SEVERITY_COMMANDS.get(issue.severity, "notice")

        # Build parameters
        params = []

        if issue.file_path:
            params.append(f"file={issue.file_path}")
        if issue.line_number:
            params.append(f"line={issue.line_number}")

        # Title includes rule ID and operation (if available)
        title_parts = [f"[{issue.rule_id}]"]
        if issue.operation:
            title_parts.append(str(issue.operation))
        title = " ".join(title_parts)
        # Escape special characters in title
        title = title.replace("%", "%25")
        title = title.replace("\n", "%0A")
        title = title.replace("\r", "%0D")
        params.append(f"title={title}")

        params_str = ",".join(params)

        # Message (escape special characters)
        message = issue.message.replace("%", "%25")
        message = message.replace("\n", "%0A")
        message = message.replace("\r", "%0D")

        return f"::{command} {params_str}::{message}"

    def report(self, issues: list[Issue]) -> str:
        """Generate GitHub annotations for the issues.

        Args:
            issues: List of issues to report.

        Returns:
            The annotations as a string.
        """
        lines = []

        if not issues:
            lines.append("::notice::No migration issues found!")
        else:
            # Group annotation
            lines.append(f"::group::Migration Safety Check ({len(issues)} issues)")

            for issue in issues:
                lines.append(self._format_annotation(issue))

            lines.append("::endgroup::")

            # Summary
            errors = sum(1 for i in issues if i.severity == Severity.ERROR)
            warnings = sum(1 for i in issues if i.severity == Severity.WARNING)

            if errors:
                lines.append(
                    f"::error::Migration check failed: "
                    f"{errors} error(s), {warnings} warning(s)"
                )

        output = "\n".join(lines)
        self.write(output)
        return output
