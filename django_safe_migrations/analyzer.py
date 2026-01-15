"""Core migration analyzer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from django_safe_migrations.conf import (
    get_excluded_apps,
    get_rule_severity,
    is_rule_disabled,
)
from django_safe_migrations.rules import get_all_rules
from django_safe_migrations.rules.base import BaseRule, Issue
from django_safe_migrations.utils import (
    get_db_vendor,
    get_migration_file_path,
    get_operation_line_number,
)

if TYPE_CHECKING:
    from django.db.migrations import Migration


class MigrationAnalyzer:
    """Analyzes Django migrations for unsafe operations.

    The analyzer checks migrations against a set of rules and returns
    any issues found. It can analyze individual migrations, all migrations
    for an app, or all migrations in the project.

    Configuration can be provided via Django settings::

        SAFE_MIGRATIONS = {
            "DISABLED_RULES": ["SM006", "SM008"],
            "RULE_SEVERITY": {"SM002": "INFO"},
            "EXCLUDED_APPS": ["myapp"],
        }

    Example:
        >>> analyzer = MigrationAnalyzer()
        >>> issues = analyzer.analyze_all()
        >>> for issue in issues:
        ...     print(issue)
    """

    def __init__(
        self,
        rules: Optional[list[BaseRule]] = None,
        db_vendor: Optional[str] = None,
        disabled_rules: Optional[list[str]] = None,
    ):
        """Initialize the analyzer.

        Args:
            rules: List of rules to check. If None, all rules for the
                   database vendor will be used.
            db_vendor: Database vendor (e.g., 'postgresql'). If None,
                       it will be detected from Django settings.
            disabled_rules: List of rule IDs to disable. If None, uses
                           SAFE_MIGRATIONS["DISABLED_RULES"] from settings.
        """
        self.db_vendor = db_vendor or get_db_vendor()
        self._disabled_rules = disabled_rules
        self.rules = rules or get_all_rules(self.db_vendor)

    def _is_rule_disabled(self, rule_id: str) -> bool:
        """Check if a rule is disabled.

        Args:
            rule_id: The rule ID to check.

        Returns:
            True if the rule should be skipped.
        """
        if self._disabled_rules is not None:
            return rule_id in self._disabled_rules
        return is_rule_disabled(rule_id)

    def analyze_migration(
        self,
        migration: Migration,
        app_label: Optional[str] = None,
        migration_name: Optional[str] = None,
    ) -> list[Issue]:
        """Analyze a single migration for issues.

        Args:
            migration: The Django migration to analyze.
            app_label: Optional app label override.
            migration_name: Optional migration name override.

        Returns:
            A list of Issue objects found in the migration.
        """
        issues: list[Issue] = []

        # Get metadata
        file_path = get_migration_file_path(migration)
        if app_label is None:
            app_label = getattr(migration, "app_label", None)
        if migration_name is None:
            migration_name = getattr(migration, "name", None)

        operations = getattr(migration, "operations", [])

        for idx, operation in enumerate(operations):
            for rule in self.rules:
                # Skip disabled rules
                if self._is_rule_disabled(rule.rule_id):
                    continue

                # Skip rules that don't apply to this database
                if not rule.applies_to_db(self.db_vendor):
                    continue

                issue = rule.check(
                    operation=operation,
                    migration=migration,
                    db_vendor=self.db_vendor,
                )

                if issue:
                    # Apply severity override from settings
                    issue.severity = get_rule_severity(issue.rule_id, issue.severity)

                    # Enrich issue with context
                    if issue.file_path is None:
                        issue.file_path = file_path
                    if issue.line_number is None:
                        issue.line_number = get_operation_line_number(migration, idx)
                    if issue.app_label is None:
                        issue.app_label = app_label
                    if issue.migration_name is None:
                        issue.migration_name = migration_name

                    issues.append(issue)

        return issues

    def analyze_app(self, app_label: str) -> list[Issue]:
        """Analyze all migrations for a Django app.

        Args:
            app_label: The app label (e.g., 'myapp').

        Returns:
            A list of Issue objects found in the app's migrations.
        """
        from django.db.migrations.loader import MigrationLoader

        issues: list[Issue] = []
        loader = MigrationLoader(None, ignore_no_migrations=True)

        # Get all migrations for this app from disk_migrations
        app_migrations = [
            (name, loader.get_migration(app, name))
            for (app, name) in loader.disk_migrations.keys()
            if app == app_label
        ]

        # Sort by migration name
        app_migrations.sort(key=lambda x: x[0])

        for name, migration in app_migrations:
            issues.extend(
                self.analyze_migration(
                    migration=migration,
                    app_label=app_label,
                    migration_name=name,
                )
            )

        return issues

    def analyze_all(
        self,
        exclude_apps: Optional[list[str]] = None,
    ) -> list[Issue]:
        """Analyze all migrations in the project.

        Args:
            exclude_apps: List of app labels to exclude (e.g., Django's
                          built-in apps). If None, uses
                          SAFE_MIGRATIONS["EXCLUDED_APPS"] from settings.

        Returns:
            A list of Issue objects found in all migrations.
        """
        from django.db.migrations.loader import MigrationLoader

        if exclude_apps is None:
            exclude_apps = get_excluded_apps()

        issues: list[Issue] = []
        loader = MigrationLoader(None, ignore_no_migrations=True)

        # Get all apps with migrations from disk_migrations
        apps_with_migrations = set(app for (app, _) in loader.disk_migrations.keys())

        for app_label in sorted(apps_with_migrations):
            if app_label in exclude_apps:
                continue
            issues.extend(self.analyze_app(app_label))

        return issues

    def analyze_new_migrations(
        self,
        app_label: Optional[str] = None,
    ) -> list[Issue]:
        """Analyze only unapplied (new) migrations.

        This is useful for CI/CD pipelines to only check migrations
        that haven't been applied yet.

        Args:
            app_label: Optional app label to filter by.

        Returns:
            A list of Issue objects found in unapplied migrations.
        """
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        issues: list[Issue] = []
        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        for key in loader.disk_migrations.keys():
            app, name = key
            # Skip if already applied
            if (app, name) in applied:
                continue

            # Skip if filtering by app
            if app_label and app != app_label:
                continue

            migration = loader.get_migration(app, name)
            issues.extend(
                self.analyze_migration(
                    migration=migration,
                    app_label=app,
                    migration_name=name,
                )
            )

        return issues

    def get_summary(self, issues: list[Issue]) -> dict[str, Any]:
        """Get a summary of the issues found.

        Args:
            issues: List of issues to summarize.

        Returns:
            A dictionary with counts by severity and rule.
        """
        summary: dict[str, Any] = {
            "total": len(issues),
            "by_severity": {
                "error": 0,
                "warning": 0,
                "info": 0,
            },
            "by_rule": {},
            "by_app": {},
        }

        for issue in issues:
            # Count by severity
            severity = issue.severity.value
            summary["by_severity"][severity] += 1

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
