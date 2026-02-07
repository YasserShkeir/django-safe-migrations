"""Console reporter with colored output."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from django_safe_migrations.reporters.base import BaseReporter
from django_safe_migrations.rules.base import Severity

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


class ConsoleReporter(BaseReporter):
    """Reporter that outputs issues to the console with colors.

    Colors are automatically disabled when output is not a TTY.
    """

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "green": "\033[92m",
        "gray": "\033[90m",
    }

    SEVERITY_COLORS = {
        Severity.ERROR: "red",
        Severity.WARNING: "yellow",
        Severity.INFO: "blue",
    }

    SEVERITY_SYMBOLS = {
        Severity.ERROR: "X",
        Severity.WARNING: "!",
        Severity.INFO: "i",
    }

    SEVERITY_SYMBOLS_UNICODE = {
        Severity.ERROR: "\u2716",
        Severity.WARNING: "\u26a0",
        Severity.INFO: "\u2139",
    }

    def __init__(
        self,
        stream: TextIO | None = None,
        use_color: bool | None = None,
        show_suggestions: bool = True,
        use_unicode: bool | None = None,
    ):
        """Initialize the console reporter.

        Args:
            stream: Output stream. Defaults to sys.stdout.
            use_color: Force color on/off. None = auto-detect.
            show_suggestions: Whether to show fix suggestions.
            use_unicode: Force Unicode symbols on/off. None = auto-detect.
        """
        super().__init__(stream or sys.stdout)
        self.show_suggestions = show_suggestions

        if use_color is None:
            # Auto-detect: use color if output is a TTY
            self.use_color = (
                self.stream is not None
                and hasattr(self.stream, "isatty")
                and self.stream.isatty()
            )
        else:
            self.use_color = use_color

        if use_unicode is None:
            self.use_unicode = self._detect_unicode_support()
        else:
            self.use_unicode = use_unicode

    @staticmethod
    def _detect_unicode_support() -> bool:
        """Detect if the terminal supports Unicode output."""
        import locale

        encoding = (
            getattr(sys.stdout, "encoding", None) or locale.getpreferredencoding()
        )
        return encoding.lower().replace("-", "") in ("utf8", "utf16", "utf32")

    @property
    def _symbols(self) -> dict[Severity, str]:
        """Return the appropriate symbol set based on Unicode support."""
        if self.use_unicode:
            return self.SEVERITY_SYMBOLS_UNICODE
        return self.SEVERITY_SYMBOLS

    def _color(self, text: str, color: str) -> str:
        """Apply ANSI color to text.

        Args:
            text: The text to colorize.
            color: The color name.

        Returns:
            Colorized text if colors are enabled, otherwise plain text.
        """
        if not self.use_color:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def _format_issue(self, issue: Issue) -> str:
        """Format a single issue for display.

        Args:
            issue: The issue to format.

        Returns:
            Formatted string.
        """
        lines = []

        # Build location string
        location_parts = []
        if issue.app_label:
            location_parts.append(issue.app_label)
        if issue.migration_name:
            location_parts.append(issue.migration_name)
        location = "/".join(location_parts) if location_parts else ""

        if issue.file_path:
            file_location = issue.file_path
            if issue.line_number:
                file_location += f":{issue.line_number}"
            location = file_location

        # Severity color and symbol
        color = self.SEVERITY_COLORS.get(issue.severity, "reset")
        symbol = self._symbols.get(issue.severity, "*")

        # Main line
        severity_badge = self._color(f"{symbol} {issue.severity.value.upper()}", color)
        rule_id = self._color(f"[{issue.rule_id}]", "cyan")

        if location:
            location_str = self._color(location, "gray")
            lines.append(f"{severity_badge} {rule_id} {location_str}")
        else:
            lines.append(f"{severity_badge} {rule_id}")

        # Message
        lines.append(f"   {issue.message}")

        # Operation
        if issue.operation:
            op_str = self._color(f"   Operation: {issue.operation}", "gray")
            lines.append(op_str)

        # Suggestion (indented)
        if self.show_suggestions and issue.suggestion:
            lines.append("")
            hint = "\U0001f4a1" if self.use_unicode else "*"
            suggestion_header = self._color(f"   {hint} Suggestion:", "green")
            lines.append(suggestion_header)
            for line in issue.suggestion.strip().split("\n"):
                lines.append(f"      {line}")

        return "\n".join(lines)

    def report(self, issues: list[Issue]) -> str:
        """Generate a console report for the issues.

        Args:
            issues: List of issues to report.

        Returns:
            The formatted report.
        """
        if not issues:
            check = "\u2713" if self.use_unicode else "*"
            output = self._color(f"{check} No migration issues found!", "green")
            self.write(output)
            return output

        lines = []

        # Header
        header = self._color(
            f"Found {len(issues)} migration issue(s):",
            "bold",
        )
        lines.append(header)
        lines.append("")

        # Group by severity for display order
        errors = [i for i in issues if i.severity == Severity.ERROR]
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        infos = [i for i in issues if i.severity == Severity.INFO]

        for issue_group in [errors, warnings, infos]:
            for issue in issue_group:
                lines.append(self._format_issue(issue))
                lines.append("")  # Blank line between issues

        # Summary
        separator = "\u2500" if self.use_unicode else "-"
        lines.append(self._color(separator * 50, "gray"))
        summary_parts = []
        if errors:
            summary_parts.append(self._color(f"{len(errors)} error(s)", "red"))
        if warnings:
            summary_parts.append(self._color(f"{len(warnings)} warning(s)", "yellow"))
        if infos:
            summary_parts.append(self._color(f"{len(infos)} info", "blue"))

        lines.append("Summary: " + ", ".join(summary_parts))

        output = "\n".join(lines)
        self.write(output)
        return output
