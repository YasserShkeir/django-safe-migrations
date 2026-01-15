"""Base classes for migration rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from django.db.migrations import Migration
    from django.db.migrations.operations.base import Operation


class Severity(Enum):
    """Severity levels for migration issues."""

    ERROR = "error"  # Will likely break production
    WARNING = "warning"  # Might cause issues under load
    INFO = "info"  # Best practice recommendation


@dataclass
class Issue:
    """Represents an issue found in a migration.

    Attributes:
        rule_id: Unique identifier for the rule (e.g., 'SM001').
        severity: How serious the issue is.
        operation: String representation of the problematic operation.
        message: Human-readable description of the issue.
        suggestion: Optional fix suggestion.
        file_path: Path to the migration file.
        line_number: Line number in the migration file.
        app_label: The Django app label.
        migration_name: The migration name (e.g., '0002_add_field').
    """

    rule_id: str
    severity: Severity
    operation: str
    message: str
    suggestion: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    app_label: Optional[str] = None
    migration_name: Optional[str] = None

    def __str__(self) -> str:
        """Return a string representation of the issue."""
        location = ""
        if self.file_path:
            location = f"{self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"
            location += " - "

        return (
            f"[{self.rule_id}] {self.severity.value.upper()}: "
            f"{location}{self.message}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the issue to a dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "operation": self.operation,
            "message": self.message,
            "suggestion": self.suggestion,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "app_label": self.app_label,
            "migration_name": self.migration_name,
        }


class BaseRule(ABC):
    """Base class for all migration rules.

    Subclasses must implement:
    - rule_id: Unique identifier (e.g., 'SM001')
    - severity: Default severity level
    - description: Human-readable description
    - check(): Method to detect the issue
    """

    rule_id: str
    severity: Severity
    description: str
    db_vendors: list[str] = []  # Empty means all databases

    @abstractmethod
    def check(
        self,
        operation: Operation,
        migration: Migration,
        **kwargs: Any,
    ) -> Optional[Issue]:
        """Check if an operation violates this rule.

        Args:
            operation: The Django migration operation to check.
            migration: The migration containing the operation.
            **kwargs: Additional context (e.g., db_vendor).

        Returns:
            An Issue if a violation is found, None otherwise.
        """
        raise NotImplementedError

    def get_suggestion(self, operation: Operation) -> Optional[str]:
        """Return a fix suggestion for the operation.

        Args:
            operation: The problematic operation.

        Returns:
            A string with the suggested fix, or None.
        """
        return None

    def applies_to_db(self, db_vendor: str) -> bool:
        """Check if this rule applies to the given database vendor.

        Args:
            db_vendor: The database vendor (e.g., 'postgresql').

        Returns:
            True if the rule applies, False otherwise.
        """
        if not self.db_vendors:
            return True
        return db_vendor in self.db_vendors

    def create_issue(
        self,
        operation: Operation,
        message: str,
        migration: Optional[Migration] = None,
        suggestion: Optional[str] = None,
        **kwargs: Any,
    ) -> Issue:
        """Create an Issue with common fields populated.

        Args:
            operation: The problematic operation.
            message: The issue message.
            migration: The migration containing the operation.
            suggestion: Optional fix suggestion.
            **kwargs: Additional Issue fields.

        Returns:
            A populated Issue instance.
        """
        from django_safe_migrations.utils import (
            format_operation_name,
            get_migration_file_path,
        )

        file_path = None
        app_label = None
        migration_name = None

        if migration:
            file_path = get_migration_file_path(migration)
            if hasattr(migration, "app_label"):
                app_label = migration.app_label
            if hasattr(migration, "name"):
                migration_name = migration.name

        return Issue(
            rule_id=self.rule_id,
            severity=self.severity,
            operation=format_operation_name(operation),
            message=message,
            suggestion=suggestion or self.get_suggestion(operation),
            file_path=file_path,
            app_label=app_label,
            migration_name=migration_name,
            **kwargs,
        )
