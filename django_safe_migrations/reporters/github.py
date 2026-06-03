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

    @staticmethod
    def _escape_data(value: str) -> str:
        r"""Escape a workflow-command message (the text after ``::``).

        Per GitHub's spec, message data must escape ``%``, ``\r``, ``\n``.
        """
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    @classmethod
    def _escape_property(cls, value: str) -> str:
        r"""Escape a workflow-command property value (e.g. ``file=``/``title=``).

        Property values are comma-separated and colon-delimited, so in
        addition to the message escapes they must also escape ``:`` and
        ``,`` (otherwise a filename like ``C:\a,b`` corrupts the command).
        """
        return cls._escape_data(value).replace(":", "%3A").replace(",", "%2C")

    def _format_annotation(self, issue: Issue) -> str:
        """Format an issue as a GitHub workflow command.

        Args:
            issue: The issue to format.

        Returns:
            GitHub workflow command string.
        """
        command = self.SEVERITY_COMMANDS.get(issue.severity, "notice")

        # Build parameters (property values need the stricter escaping)
        params = []

        if issue.file_path:
            params.append(f"file={self._escape_property(issue.file_path)}")
        if issue.line_number:
            params.append(f"line={issue.line_number}")

        # Title includes rule ID and operation (if available)
        title_parts = [f"[{issue.rule_id}]"]
        if issue.operation:
            title_parts.append(str(issue.operation))
        title = " ".join(title_parts)
        params.append(f"title={self._escape_property(title)}")

        params_str = ",".join(params)

        # Message uses the data (non-property) escaping
        message = self._escape_data(issue.message)

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
