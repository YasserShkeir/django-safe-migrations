"""SARIF (Static Analysis Results Interchange Format) reporter.

This module outputs issues in SARIF 2.1.0 format, which is compatible
with GitHub Code Scanning and other security tools.

For more information about SARIF:
https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any, TextIO

from django_safe_migrations.reporters.base import BaseReporter
from django_safe_migrations.rules import ALL_RULES

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue, Severity


# SARIF schema version
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "master/Schemata/sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"


def _severity_to_sarif_level(severity: Severity) -> str:
    """Convert our Severity to SARIF level.

    Args:
        severity: The issue severity.

    Returns:
        SARIF level string: "error", "warning", or "note".
    """
    from django_safe_migrations.rules.base import Severity

    mapping = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "note",
    }
    return mapping.get(severity, "note")


def _get_rule_info() -> dict[str, dict[str, str]]:
    """Get information about all rules for SARIF output.

    Returns:
        Dictionary mapping rule_id to rule information.
    """
    rule_info = {}
    for rule_cls in ALL_RULES:
        rule = rule_cls()
        rule_info[rule.rule_id] = {
            "id": rule.rule_id,
            "name": rule.__class__.__name__,
            "description": rule.description,
            "severity": rule.severity.value,
        }
    return rule_info


class SarifReporter(BaseReporter):
    """Reporter that outputs issues in SARIF 2.1.0 format.

    SARIF (Static Analysis Results Interchange Format) is a standard
    format for the output of static analysis tools. It's supported by
    GitHub Code Scanning, Azure DevOps, and many other tools.

    Example usage with GitHub Actions:

        ```yaml
        - name: Check migrations
          run: python manage.py check_migrations --format=sarif --output=results.sarif

        - name: Upload SARIF
          uses: github/codeql-action/upload-sarif@v2
          with:
            sarif_file: results.sarif
        ```
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        pretty: bool = True,
        tool_version: str | None = None,
    ):
        """Initialize the SARIF reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
            pretty: Whether to pretty-print the JSON.
            tool_version: Version of django-safe-migrations. Auto-detected if None.
        """
        super().__init__(stream or sys.stdout)
        self.pretty = pretty
        self._tool_version = tool_version

    @property
    def tool_version(self) -> str:
        """Get the tool version."""
        if self._tool_version:
            return self._tool_version
        try:
            from django_safe_migrations import __version__

            return __version__
        except ImportError:
            return "unknown"

    def report(self, issues: list[Issue]) -> str:
        """Generate a SARIF report for the issues.

        Args:
            issues: List of issues to report.

        Returns:
            The SARIF report as a JSON string.
        """
        sarif_data = self._build_sarif(issues)

        if self.pretty:
            output = json.dumps(sarif_data, indent=2)
        else:
            output = json.dumps(sarif_data)

        self.write(output)
        return output

    def _build_sarif(self, issues: list[Issue]) -> dict[str, Any]:
        """Build the complete SARIF structure.

        Args:
            issues: List of issues to include.

        Returns:
            Complete SARIF data structure.
        """
        return {
            "$schema": SARIF_SCHEMA,
            "version": SARIF_VERSION,
            "runs": [self._build_run(issues)],
        }

    def _build_run(self, issues: list[Issue]) -> dict[str, Any]:
        """Build a SARIF run object.

        Args:
            issues: List of issues for this run.

        Returns:
            SARIF run object.
        """
        return {
            "tool": self._build_tool(),
            "results": [self._build_result(issue) for issue in issues],
            "invocations": [
                {
                    "executionSuccessful": True,
                }
            ],
        }

    def _build_tool(self) -> dict[str, Any]:
        """Build the SARIF tool descriptor.

        Returns:
            SARIF tool object with driver information.
        """
        rule_info = _get_rule_info()

        rules = [
            {
                "id": info["id"],
                "name": info["name"],
                "shortDescription": {"text": info["description"]},
                "fullDescription": {"text": info["description"]},
                "defaultConfiguration": {
                    "level": _severity_to_sarif_level_from_str(info["severity"]),
                },
                "helpUri": (
                    "https://github.com/YasserShkeir/"
                    "django-safe-migrations/blob/main/docs/rules.md"
                ),
            }
            for info in rule_info.values()
        ]

        return {
            "driver": {
                "name": "django-safe-migrations",
                "version": self.tool_version,
                "informationUri": (
                    "https://github.com/YasserShkeir/django-safe-migrations"
                ),
                "rules": rules,
            }
        }

    def _build_result(self, issue: Issue) -> dict[str, Any]:
        """Build a SARIF result object for an issue.

        Args:
            issue: The issue to convert.

        Returns:
            SARIF result object.
        """
        result: dict[str, Any] = {
            "ruleId": issue.rule_id,
            "level": _severity_to_sarif_level(issue.severity),
            "message": {"text": issue.message},
        }

        # Add location if available
        if issue.file_path:
            # Convert absolute paths to relative for GitHub Code Scanning
            file_uri = issue.file_path
            if os.path.isabs(file_uri):
                try:
                    file_uri = os.path.relpath(file_uri)
                except ValueError:
                    pass  # On Windows, relpath can fail across drives

            location: dict[str, Any] = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": file_uri,
                        "uriBaseId": "%SRCROOT%",
                    }
                }
            }

            if issue.line_number:
                location["physicalLocation"]["region"] = {
                    "startLine": issue.line_number,
                }

            result["locations"] = [location]

        # Add fix suggestion if available
        if issue.suggestion:
            result["fixes"] = [
                {
                    "description": {"text": issue.suggestion},
                }
            ]

        return result


def _severity_to_sarif_level_from_str(severity_str: str) -> str:
    """Convert severity string to SARIF level.

    Args:
        severity_str: Severity as string ("error", "warning", "info").

    Returns:
        SARIF level string.
    """
    mapping = {
        "error": "error",
        "warning": "warning",
        "info": "note",
    }
    return mapping.get(severity_str, "note")
