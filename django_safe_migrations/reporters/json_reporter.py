"""JSON reporter for CI/CD integration."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any, TextIO

from django_safe_migrations.reporters.base import BaseReporter

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


class JsonReporter(BaseReporter):
    """Reporter that outputs issues as JSON.

    Useful for CI/CD pipelines and integration with other tools.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        pretty: bool = False,
    ):
        """Initialize the JSON reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
            pretty: Whether to pretty-print the JSON.
        """
        super().__init__(stream or sys.stdout)
        self.pretty = pretty

    def report(self, issues: list[Issue]) -> str:
        """Generate a JSON report for the issues.

        Args:
            issues: List of issues to report.

        Returns:
            The JSON report as a string.
        """
        data: dict[str, Any] = {
            "total": len(issues),
            "issues": [issue.to_dict() for issue in issues],
            "summary": self._get_summary(issues),
        }

        if self.pretty:
            output = json.dumps(data, indent=2, sort_keys=True)
        else:
            output = json.dumps(data)

        self.write(output)
        return output

    def _get_summary(self, issues: list[Issue]) -> dict[str, Any]:
        """Generate a summary of the issues.

        Args:
            issues: List of issues to summarize.

        Returns:
            Summary dictionary.
        """
        from django_safe_migrations.rules.base import Severity

        summary: dict[str, Any] = {
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "by_rule": {},
            "by_app": {},
        }

        for issue in issues:
            # Count by severity
            if issue.severity == Severity.ERROR:
                summary["errors"] += 1
            elif issue.severity == Severity.WARNING:
                summary["warnings"] += 1
            else:
                summary["info"] += 1

            # Count by rule
            if issue.rule_id not in summary["by_rule"]:
                summary["by_rule"][issue.rule_id] = 0
            summary["by_rule"][issue.rule_id] += 1

            # Count by app
            app = issue.app_label or "unknown"
            if app not in summary["by_app"]:
                summary["by_app"][app] = 0
            summary["by_app"][app] += 1

        return summary
