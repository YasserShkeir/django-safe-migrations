"""Core migration analyzer."""

from __future__ import annotations

import hashlib
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
        cache: Optional[Any] = None,
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
            cache: Optional ``AnalysisCache``. When set, each migration's
                   issues are served from / stored to the cache keyed on a
                   dependency-aware content hash.
        """
        self.db_vendor = db_vendor or get_db_vendor()
        self._disabled_rules = disabled_rules
        self.verbose = verbose
        self.cache = cache
        # Memoise per-file SHA-256 so each migration file is hashed once per run
        # even though it appears in many migrations' dependency closures.
        self._file_hash_memo: dict[str, str] = {}
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
        loader: Optional[Any] = None,
    ) -> list[Issue]:
        """Analyze a single migration for issues.

        Args:
            migration: The Django migration to analyze.
            app_label: Optional app label override.
            migration_name: Optional migration name override.
            loader: Optional pre-built ``MigrationLoader`` reused for old-field
                    state resolution. Avoids rebuilding the loader (which reads
                    every migration on disk) for each operation.

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

        # Cache lookup: serve unchanged migrations from the cache. The content
        # hash covers this migration's file and its transitive dependencies, so
        # changes to ancestor migrations (which feed before-state resolution)
        # correctly invalidate the entry.
        cache_key: Optional[str] = None
        content_hash: Optional[str] = None
        if self.cache is not None and app_label and migration_name:
            content_hash = self._migration_content_hash(
                migration, app_label, migration_name, loader
            )
            if content_hash is not None:
                cache_key = f"{app_label}:{migration_name}"
                cached: Optional[list[Issue]] = self.cache.get(cache_key, content_hash)
                if cached is not None:
                    logger.debug("Cache hit for %s", cache_key)
                    return cached

        operations = getattr(migration, "operations", [])
        logger.debug(
            "Analyzing migration: %s.%s (%d operations)",
            app_label,
            migration_name,
            len(operations),
        )

        # Pre-parse suppression comments for efficiency
        suppressions = get_suppressions_for_migration(migration)

        from django.db import migrations as mig_module

        for idx, operation in enumerate(operations):
            # Get operation line number for suppression checking
            operation_line = get_operation_line_number(migration, idx)

            self._check_operation(
                operation=operation,
                operation_index=idx,
                operation_line=operation_line,
                migration=migration,
                app_label=app_label,
                migration_name=migration_name,
                file_path=file_path,
                suppressions=suppressions,
                loader=loader,
                issues=issues,
            )

            # Recurse into SeparateDatabaseAndState so unsafe database
            # operations hidden inside the wrapper are still analyzed.
            if isinstance(operation, mig_module.SeparateDatabaseAndState):
                for db_op in operation.database_operations or []:
                    self._check_operation(
                        operation=db_op,
                        operation_index=idx,
                        operation_line=operation_line,
                        migration=migration,
                        app_label=app_label,
                        migration_name=migration_name,
                        file_path=file_path,
                        suppressions=suppressions,
                        loader=loader,
                        issues=issues,
                    )

        # Migration-level rules: run once per migration over all operations.
        for rule in self.rules:
            if not self._is_rule_enabled(rule.rule_id, app_label):
                continue
            if not rule.applies_to_db(self.db_vendor):
                continue
            if not rule.applies_to_django():
                continue
            for issue in rule.check_migration(migration):
                issue.severity = get_rule_severity_for_app(
                    issue.rule_id, issue.severity, app_label
                )
                if issue.file_path is None:
                    issue.file_path = file_path
                if issue.app_label is None:
                    issue.app_label = app_label
                if issue.migration_name is None:
                    issue.migration_name = migration_name
                issues.append(issue)

        logger.debug(
            "Migration %s.%s analysis complete: %d issues found",
            app_label,
            migration_name,
            len(issues),
        )

        # Store the freshly computed result for next time.
        if (
            self.cache is not None
            and cache_key is not None
            and content_hash is not None
        ):
            self.cache.set(cache_key, content_hash, issues)

        return issues

    def _migration_content_hash(
        self,
        migration: Migration,
        app_label: str,
        migration_name: str,
        loader: Any,
    ) -> Optional[str]:
        """Compute a dependency-aware content hash for a migration.

        The hash combines the SHA-256 of the migration's own source file with
        those of its transitive dependencies (the graph ``forwards_plan``), so
        a change to any ancestor — which can alter before-state resolution —
        invalidates the entry. Returns ``None`` (uncacheable) if any file in
        the closure cannot be located or read, or if the graph cannot resolve
        the node (e.g. squashed/replaced migrations).

        Args:
            migration: The migration being analysed.
            app_label: Its app label.
            migration_name: Its migration name.
            loader: The active ``MigrationLoader`` (provides the graph).

        Returns:
            A hex digest, or ``None`` if the migration is not safely cacheable.
        """
        from django_safe_migrations.cache import file_sha256

        # Resolve the dependency closure to a deterministic list of file paths.
        paths: list[str] = []
        node = (app_label, migration_name)
        try:
            graph = getattr(loader, "graph", None)
            if graph is not None and node in getattr(graph, "nodes", {}):
                plan = graph.forwards_plan(node)
                for dep in plan:
                    obj = loader.disk_migrations.get(dep)
                    if obj is None:
                        return None
                    dep_path = get_migration_file_path(obj)
                    if not dep_path:
                        return None
                    paths.append(dep_path)
            else:
                # No usable graph node: fall back to the migration's own file.
                own = get_migration_file_path(migration)
                if not own:
                    return None
                paths = [own]
        except Exception:  # noqa: BLE001 - any graph error => uncacheable
            return None

        digest = hashlib.sha256()
        for path in paths:
            file_hash = self._file_hash_memo.get(path)
            if file_hash is None:
                try:
                    file_hash = file_sha256(path)
                except OSError:
                    return None
                self._file_hash_memo[path] = file_hash
            digest.update(file_hash.encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _check_operation(
        self,
        operation: Any,
        operation_index: int,
        operation_line: Optional[int],
        migration: Migration,
        app_label: Optional[str],
        migration_name: Optional[str],
        file_path: Optional[str],
        suppressions: Any,
        loader: Any,
        issues: list[Issue],
    ) -> None:
        """Run all enabled rules against a single operation.

        The old-field state for ``AlterField`` operations is resolved once
        per operation (not once per rule), avoiding a redundant rebuild of
        the migration state for every rule. Matching issues are appended to
        ``issues`` in place.
        """
        from django.db import migrations as mig_module

        # Resolve old field state once per operation (shared by all rules).
        is_alter_field = (
            isinstance(operation, mig_module.AlterField)
            and bool(app_label)
            and bool(migration_name)
        )
        old_field = None
        if is_alter_field:
            old_field = resolve_field_before_operation(
                app_label=app_label,  # type: ignore[arg-type]
                migration_name=migration_name,  # type: ignore[arg-type]
                operation_index=operation_index,
                model_name=operation.model_name,
                field_name=operation.name,
                loader=loader,
            )

        for rule in self.rules:
            # Skip disabled rules (individual, category-based, or per-app)
            if not self._is_rule_enabled(rule.rule_id, app_label):
                continue

            # Skip rules that don't apply to this database
            if not rule.applies_to_db(self.db_vendor):
                continue

            # Skip rules that require a newer Django than is installed
            if not rule.applies_to_django():
                continue

            # Check for inline suppression comments
            if file_path and operation_line:
                if is_operation_suppressed(
                    file_path, operation_line, rule.rule_id, suppressions
                ):
                    continue

            rule_kwargs: dict[str, object] = {"db_vendor": self.db_vendor}
            if is_alter_field:
                rule_kwargs["old_field"] = old_field

            issue = rule.check(
                operation=operation,
                migration=migration,
                **rule_kwargs,
            )
            if not issue:
                continue

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
            if issue.operation_index is None:
                issue.operation_index = operation_index

            logger.debug(
                "Found issue: %s in %s.%s at line %s",
                issue.rule_id,
                app_label,
                migration_name,
                operation_line,
            )
            issues.append(issue)

    def analyze_app(self, app_label: str, loader: Any = None) -> list[Issue]:
        """Analyze all migrations for a Django app.

        Args:
            app_label: The app label (e.g., 'myapp').
            loader: Optional pre-built ``MigrationLoader`` to reuse instead of
                    constructing a new one (which re-reads every migration).

        Returns:
            A list of Issue objects found in the app's migrations.
        """
        from django.db.migrations.loader import MigrationLoader

        issues: list[Issue] = []
        if loader is None:
            loader = MigrationLoader(None, ignore_no_migrations=True)

        # Get all migrations for this app from disk_migrations.
        # Use disk_migrations values directly instead of get_migration()
        # because get_migration() uses graph.nodes, which may not contain
        # replaced/squashed migrations (causing KeyError).
        app_migrations = [
            (name, migration)
            for (app, name), migration in loader.disk_migrations.items()
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
                    loader=loader,
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
            issues.extend(self.analyze_app(app_label, loader=loader))

        logger.info("Analysis complete: %d total issues found", len(issues))
        if self.verbose:
            print(f"Analysis complete: {len(issues)} issue(s) found", file=sys.stderr)
        return issues

    def analyze_new_migrations(
        self,
        app_label: Optional[str] = None,
        exclude_apps: Optional[list[str]] = None,
    ) -> list[Issue]:
        """Analyze only unapplied (new) migrations.

        This is useful for CI/CD pipelines to only check migrations
        that haven't been applied yet.

        Args:
            app_label: Optional app label to filter by.
            exclude_apps: List of app labels to exclude (e.g., Django's
                          built-in apps). If None, uses
                          SAFE_MIGRATIONS["EXCLUDED_APPS"] from settings.

        Returns:
            A list of Issue objects found in unapplied migrations.
        """
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        if exclude_apps is None:
            exclude_apps = get_excluded_apps()

        issues: list[Issue] = []
        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        unapplied_count = 0
        for key in loader.disk_migrations.keys():
            app, name = key
            # Skip excluded apps (Django built-ins, user-configured)
            if app in exclude_apps:
                continue

            # Skip if already applied
            if (app, name) in applied:
                continue

            # Skip if filtering by app
            if app_label and app != app_label:
                continue

            unapplied_count += 1
            logger.debug("Checking unapplied migration: %s.%s", app, name)

            migration = loader.disk_migrations[(app, name)]
            issues.extend(
                self.analyze_migration(
                    migration=migration,
                    app_label=app,
                    migration_name=name,
                    loader=loader,
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
