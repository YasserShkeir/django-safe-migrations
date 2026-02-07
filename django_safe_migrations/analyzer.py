"""Core migration analyzer."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, Optional

from django_safe_migrations.conf import (
    get_excluded_apps,
    get_rule_severity_for_app,
    is_rule_enabled_for_app,
)
from django_safe_migrations.rules import get_all_rules
from django_safe_migrations.rules.base import BaseRule, Issue
from django_safe_migrations.suppression import (
    get_suppressions_for_migration,
    is_operation_suppressed,
)
from django_safe_migrations.utils import (
    get_db_vendor,
    get_migration_file_path,
    get_operation_line_number,
    resolve_field_before_operation,
)

if TYPE_CHECKING:
    from django.db.migrations import Migration

logger = logging.getLogger("django_safe_migrations")


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
        verbose: bool = False,
    ):
        """Initialize the analyzer.

        Args:
            rules: List of rules to check. If None, all rules for the
                   database vendor will be used.
            db_vendor: Database vendor (e.g., 'postgresql'). If None,
                       it will be detected from Django settings.
            disabled_rules: List of rule IDs to disable. If None, uses
                           SAFE_MIGRATIONS["DISABLED_RULES"] from settings.
            verbose: If True, print progress information to stderr.
        """
        self.db_vendor = db_vendor or get_db_vendor()
        self._disabled_rules = disabled_rules
        self.verbose = verbose
        self.rules = rules or get_all_rules(self.db_vendor)
        logger.debug(
            "Initialized analyzer: db_vendor=%s, rules=%d, disabled_rules=%s",
            self.db_vendor,
            len(self.rules),
            self._disabled_rules,
        )

    def _is_rule_enabled(self, rule_id: str, app_label: Optional[str] = None) -> bool:
        """Check if a rule is enabled.

        Checks individual rule disables, category-based disables, and
        per-app configuration.

        Args:
            rule_id: The rule ID to check.
            app_label: Optional app label for per-app configuration.

        Returns:
            True if the rule should run, False if it should be skipped.
        """
        # If explicit disabled_rules list provided to constructor, use that
        if self._disabled_rules is not None:
            return rule_id not in self._disabled_rules
        # Otherwise, use full configuration (individual + category + per-app)
        return is_rule_enabled_for_app(rule_id, app_label)

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
        logger.debug(
            "Analyzing migration: %s.%s (%d operations)",
            app_label,
            migration_name,
            len(operations),
        )

        # Pre-parse suppression comments for efficiency
        suppressions = get_suppressions_for_migration(migration)

        for idx, operation in enumerate(operations):
            # Get operation line number for suppression checking
            operation_line = get_operation_line_number(migration, idx)

            for rule in self.rules:
                # Skip disabled rules (individual, category-based, or per-app)
                if not self._is_rule_enabled(rule.rule_id, app_label):
                    logger.debug(
                        "Skipping rule %s: disabled for app %s",
                        rule.rule_id,
                        app_label,
                    )
                    continue

                # Skip rules that don't apply to this database
                if not rule.applies_to_db(self.db_vendor):
                    logger.debug(
                        "Skipping rule %s: does not apply to %s",
                        rule.rule_id,
                        self.db_vendor,
                    )
                    continue

                # Check for inline suppression comments
                if file_path and operation_line:
                    if is_operation_suppressed(
                        file_path, operation_line, rule.rule_id, suppressions
                    ):
                        logger.debug(
                            "Skipping rule %s: suppressed at line %d",
                            rule.rule_id,
                            operation_line,
                        )
                        continue

                # Resolve old field state for AlterField operations
                rule_kwargs: dict[str, object] = {
                    "db_vendor": self.db_vendor,
                }
                from django.db import migrations as mig_module

                if (
                    isinstance(operation, mig_module.AlterField)
                    and app_label
                    and migration_name
                ):
                    old_field = resolve_field_before_operation(
                        app_label=app_label,
                        migration_name=migration_name,
                        operation_index=idx,
                        model_name=operation.model_name,
                        field_name=operation.name,
                    )
                    rule_kwargs["old_field"] = old_field

                issue = rule.check(
                    operation=operation,
                    migration=migration,
                    **rule_kwargs,
                )

                if issue:
                    # Apply severity override from settings (per-app or global)
                    issue.severity = get_rule_severity_for_app(
                        issue.rule_id, issue.severity, app_label
                    )

                    # Enrich issue with context
                    if issue.file_path is None:
                        issue.file_path = file_path
                    if issue.line_number is None:
                        issue.line_number = operation_line
                    if issue.app_label is None:
                        issue.app_label = app_label
                    if issue.migration_name is None:
                        issue.migration_name = migration_name

                    logger.debug(
                        "Found issue: %s in %s.%s at line %s",
                        issue.rule_id,
                        app_label,
                        migration_name,
                        operation_line,
                    )
                    issues.append(issue)

        logger.debug(
            "Migration %s.%s analysis complete: %d issues found",
            app_label,
            migration_name,
            len(issues),
        )
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
        logger.debug("Analyzing app %s: %d migrations", app_label, len(app_migrations))
        if self.verbose:
            print(
                f"  Checking {app_label} ({len(app_migrations)} migrations)...",
                file=sys.stderr,
            )

        for name, migration in app_migrations:
            issues.extend(
                self.analyze_migration(
                    migration=migration,
                    app_label=app_label,
                    migration_name=name,
                )
            )

        logger.debug("App %s analysis complete: %d issues", app_label, len(issues))
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
        logger.debug(
            "Analyzing all apps: %d apps, excluding %s",
            len(apps_with_migrations),
            exclude_apps,
        )

        checked_apps = sorted(a for a in apps_with_migrations if a not in exclude_apps)
        if self.verbose:
            print(
                f"Analyzing {len(checked_apps)} app(s) "
                f"({len(apps_with_migrations) - len(checked_apps)} excluded)...",
                file=sys.stderr,
            )

        for app_label in sorted(apps_with_migrations):
            if app_label in exclude_apps:
                logger.debug("Skipping excluded app: %s", app_label)
                continue
            issues.extend(self.analyze_app(app_label))

        logger.info("Analysis complete: %d total issues found", len(issues))
        if self.verbose:
            print(f"Analysis complete: {len(issues)} issue(s) found", file=sys.stderr)
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

        unapplied_count = 0
        for key in loader.disk_migrations.keys():
            app, name = key
            # Skip if already applied
            if (app, name) in applied:
                continue

            # Skip if filtering by app
            if app_label and app != app_label:
                continue

            unapplied_count += 1
            logger.debug("Checking unapplied migration: %s.%s", app, name)

            migration = loader.get_migration(app, name)
            issues.extend(
                self.analyze_migration(
                    migration=migration,
                    app_label=app,
                    migration_name=name,
                )
            )

        logger.info(
            "Analyzed %d unapplied migrations: %d issues found",
            unapplied_count,
            len(issues),
        )
        return issues

    @staticmethod
    def get_summary(issues: list[Issue]) -> dict[str, Any]:
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
