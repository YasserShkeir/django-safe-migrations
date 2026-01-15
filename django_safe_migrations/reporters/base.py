"""Base reporter class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


class BaseReporter(ABC):
    """Base class for all reporters.

    Reporters are responsible for formatting and outputting issues
    found during migration analysis.
    """

    def __init__(self, stream: TextIO | None = None):
        """Initialize the reporter.

        Args:
            stream: The output stream. Defaults to stdout.
        """
        self.stream = stream

    @abstractmethod
    def report(self, issues: list[Issue]) -> str:
        """Generate a report for the given issues.

        Args:
            issues: List of issues to report.

        Returns:
            The formatted report as a string.
        """
        raise NotImplementedError

    def write(self, content: str) -> None:
        """Write content to the output stream.

        Args:
            content: The content to write.
        """
        if self.stream:
            self.stream.write(content)
            self.stream.write("\n")
