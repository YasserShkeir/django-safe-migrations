"""Management command to check migrations for unsafe operations."""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from django.core.management.base import BaseCommand, CommandParser

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.conf import (
    get_category_for_rule,
    get_database_vendor,
    get_fail_on_warning,
    get_warnings_as_errors,
    log_config_warnings,
)
from django_safe_migrations.reporters import get_reporter
from django_safe_migrations.rules import ALL_RULES, _load_extra_rules
from django_safe_migrations.rules.base import Issue, Severity


class Command(BaseCommand):
    """Check Django migrations for unsafe operations.

    This command analyzes migrations and reports issues that could
    cause problems in production, such as:

    - Adding NOT NULL columns without defaults
    - Creating indexes without CONCURRENTLY
    - Dropping columns/tables unsafely

    Usage:
        python manage.py check_migrations
        python manage.py check_migrations myapp
        python manage.py check_migrations --new-only
        python manage.py check_migrations --format=json
        python manage.py check_migrations --format=gitlab
        python manage.py check_migrations --interactive
        python manage.py check_migrations --diff main
    """

    help = "Check migrations for unsafe operations"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command arguments.

        Args:
            parser: The argument parser.
        """
        parser.add_argument(
            "app_labels",
            nargs="*",
            help="App labels to check. If empty, checks all apps.",
        )
        parser.add_argument(
            "--format",
            choices=["console", "json", "github", "gitlab", "sarif"],
            default="console",
            help="Output format (default: console)",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (defaults to stdout)",
        )
        parser.add_argument(
            "--fail-on-warning",
            action="store_true",
            help="Exit with error code on warnings (not just errors)",
        )
        parser.add_argument(
            "--new-only",
            action="store_true",
            help="Only check unapplied migrations",
        )
        parser.add_argument(
            "--no-suggestions",
            action="store_true",
            help="Hide fix suggestions in output",
        )
        parser.add_argument(
            "--exclude-apps",
            nargs="*",
            default=[],
            help="Apps to exclude from checking",
        )
        parser.add_argument(
            "--include-django-apps",
            action="store_true",
            help="Include Django's built-in apps (auth, admin, etc.)",
        )
        parser.add_argument(
            "--list-rules",
            action="store_true",
            help="List all available rules and exit",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show progress information during analysis",
        )
        parser.add_argument(
            "--interactive",
            action="store_true",
            help="Interactively review each issue",
        )
        parser.add_argument(
            "--diff",
            nargs="?",
            const="main",
            default=None,
            metavar="BASE_REF",
            help="Only check migrations changed since BASE_REF (default: main)",
        )
        parser.add_argument(
            "--since-commit",
            type=str,
            default=None,
            metavar="COMMIT",
            help=(
                "Only check migrations committed in the range COMMIT..HEAD "
                "(committed changes only; ignores the working tree)"
            ),
        )
        parser.add_argument(
            "--baseline",
            type=str,
            default=None,
            metavar="FILE",
            help="Exclude issues present in baseline file",
        )
        parser.add_argument(
            "--generate-baseline",
            type=str,
            default=None,
            metavar="FILE",
            help="Generate baseline file from current issues and exit",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Watch migration files for changes and re-run analysis",
        )
        parser.add_argument(
            "--database-vendor",
            choices=["postgresql", "mysql", "sqlite", "mariadb"],
            default=None,
            help="Override the detected database vendor for rule analysis",
        )
        parser.add_argument(
            "--warnings-as-errors",
            type=str,
            default=None,
            metavar="SM002,SM003",
            help="Comma-separated rule IDs whose warnings should fail (exit 1)",
        )
        parser.add_argument(
            "--cache",
            action="store_true",
            help="Cache analysis results to speed up repeat runs",
        )
        parser.add_argument(
            "--cache-file",
            type=str,
            default=None,
            metavar="PATH",
            help="Path to the cache file (implies --cache)",
        )

    def list_rules(self, output_format: str) -> None:
        """List all available rules.

        Lists both built-in rules and any custom rules configured via EXTRA_RULES.

        Args:
            output_format: Output format ('console' or 'json').
        """
        # Collect both built-in and custom rules
        all_rule_classes = list(ALL_RULES) + _load_extra_rules()

        rules_data = []
        for rule_cls in all_rule_classes:
            rule = rule_cls()
            categories = get_category_for_rule(rule.rule_id)
            db_vendors = rule.db_vendors if rule.db_vendors else ["all"]

            rules_data.append(
                {
                    "rule_id": rule.rule_id,
                    "severity": rule.severity.value,
                    "description": rule.description,
                    "categories": categories,
                    "db_vendors": db_vendors,
                }
            )

        if output_format == "json":
            self.stdout.write(json.dumps(rules_data, indent=2))
        else:
            # Console table format
            self.stdout.write("Available Rules:")
            self.stdout.write("-" * 80)
            for rule_info in rules_data:
                severity_str = str(rule_info["severity"]).upper()
                categories_str = ", ".join(rule_info["categories"]) or "none"
                db_str = ", ".join(rule_info["db_vendors"])
                desc = rule_info["description"]
                self.stdout.write(f"{rule_info['rule_id']} [{severity_str}] {desc}")
                self.stdout.write(f"    Categories: {categories_str}")
                self.stdout.write(f"    Databases: {db_str}")
                self.stdout.write("")

    @staticmethod
    def _load_migration(
        analyzer: MigrationAnalyzer, app_label: str, migration_name: str
    ) -> Any:
        """Load a specific migration by app label and name.

        Args:
            analyzer: The migration analyzer instance (unused but kept for API).
            app_label: The app label (e.g., 'myapp').
            migration_name: The migration name (e.g., '0001_initial').

        Returns:
            The Django migration object.

        Raises:
            CommandError: If the migration cannot be found.
        """
        from django.core.management.base import CommandError
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(None, ignore_no_migrations=True)
        key = (app_label, migration_name)
        if key in loader.disk_migrations:
            return loader.disk_migrations[key]
        raise CommandError(
            f"Migration '{migration_name}' not found for app '{app_label}'."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments.
            **options: Command options.
        """
        output_format = options["format"]

        # Handle --list-rules
        if options.get("list_rules"):
            self.list_rules(output_format)
            return

        # Validate configuration and log any warnings
        log_config_warnings()

        # Handle --watch mode
        if options.get("watch"):
            from django_safe_migrations.watch import watch_migrations

            watch_migrations()
            return

        app_labels = options["app_labels"]
        output_file = options["output"]
        # CLI flag OR the settings-level FAIL_ON_WARNING setting
        fail_on_warning = options["fail_on_warning"] or get_fail_on_warning()
        new_only = options["new_only"]
        show_suggestions = not options["no_suggestions"]
        cli_exclude_apps = options["exclude_apps"]
        include_django_apps = options["include_django_apps"]
        verbose = options.get("verbose", False)

        # Database-vendor override: CLI flag, else DATABASE_VENDOR setting, else
        # auto-detect (None).
        db_vendor_override = options.get("database_vendor") or get_database_vendor()

        # Rule IDs whose warnings should fail the build (CLI + setting).
        warnings_as_errors = set(get_warnings_as_errors())
        if options.get("warnings_as_errors"):
            warnings_as_errors.update(
                rid.strip()
                for rid in options["warnings_as_errors"].split(",")
                if rid.strip()
            )

        # Build exclude list by merging CLI args with settings-level EXCLUDED_APPS
        from django_safe_migrations.conf import get_excluded_apps

        settings_exclude_apps = get_excluded_apps()
        exclude_apps = list(set(cli_exclude_apps + settings_exclude_apps))

        if not include_django_apps:
            django_apps = [
                "admin",
                "auth",
                "contenttypes",
                "sessions",
                "messages",
                "staticfiles",
            ]
            exclude_apps = list(set(exclude_apps + django_apps))

        # Create analyzer
        analyzer = MigrationAnalyzer(db_vendor=db_vendor_override, verbose=verbose)

        # Optional result cache (--cache / --cache-file). Opt-in; namespaced by
        # a fingerprint so upgrades / config changes never serve stale results.
        cache = None
        if options.get("cache") or options.get("cache_file"):
            from django_safe_migrations.cache import (
                DEFAULT_CACHE_FILE,
                AnalysisCache,
                compute_fingerprint,
            )

            cache_path = options.get("cache_file") or DEFAULT_CACHE_FILE
            fingerprint = compute_fingerprint(
                analyzer.db_vendor, [r.rule_id for r in analyzer.rules]
            )
            cache = AnalysisCache(cache_path, fingerprint)
            analyzer.cache = cache

        # Collect issues
        issues: list[Issue] = []

        diff_ref = options.get("diff")
        since_commit = options.get("since_commit")
        if diff_ref is not None and since_commit is not None:
            self.stderr.write(
                self.style.ERROR("Use only one of --diff and --since-commit.")
            )
            sys.exit(2)
        if diff_ref is not None or since_commit is not None:
            from django.core.management.base import CommandError

            from django_safe_migrations.diff import (
                DiffError,
                get_changed_apps_and_migrations,
                get_committed_apps_and_migrations,
            )

            try:
                if since_commit is not None:
                    changed = get_committed_apps_and_migrations(since_commit)
                    mode_desc = f"committed since {since_commit}"
                else:
                    # Reachable only when diff_ref is set (the two are mutually
                    # exclusive and at least one is non-None to enter here).
                    assert diff_ref is not None
                    changed = get_changed_apps_and_migrations(diff_ref)
                    mode_desc = f"changed vs {diff_ref}"
            except DiffError as e:
                self.stderr.write(self.style.ERROR(str(e)))
                sys.exit(2)

            if verbose:
                self.stderr.write(
                    f"Diff mode ({mode_desc}): checking " f"{len(changed)} migration(s)"
                )
            for app_label, migration_name in changed:
                if app_label in exclude_apps:
                    continue
                # A changed file may not resolve to a known migration (e.g.
                # an app whose label differs from its directory, an app not
                # in INSTALLED_APPS, or a non-migration .py under a
                # ``migrations/`` directory). Warn and skip rather than
                # aborting the entire run.
                try:
                    migration = self._load_migration(
                        analyzer, app_label, migration_name
                    )
                except CommandError as e:
                    self.stderr.write(self.style.WARNING(f"Skipping: {e}"))
                    continue
                issues.extend(
                    analyzer.analyze_migration(
                        migration=migration,
                        app_label=app_label,
                        migration_name=migration_name,
                    )
                )
        elif new_only:
            if app_labels:
                for app_label in app_labels:
                    issues.extend(
                        analyzer.analyze_new_migrations(
                            app_label, exclude_apps=exclude_apps
                        )
                    )
            else:
                issues.extend(
                    analyzer.analyze_new_migrations(exclude_apps=exclude_apps)
                )
        elif app_labels:
            for app_label in app_labels:
                if app_label not in exclude_apps:
                    issues.extend(analyzer.analyze_app(app_label))
        else:
            issues.extend(analyzer.analyze_all(exclude_apps=exclude_apps))

        # Persist the cache (best-effort) once analysis is complete.
        if cache is not None:
            cache.save()
            if verbose:
                self.stderr.write(
                    f"Cache: {cache.hits} hit(s), {cache.misses} miss(es)"
                )

        # Apply baseline filtering
        baseline_path = options.get("baseline")
        if baseline_path:
            from django_safe_migrations.baseline import (
                filter_baselined_issues,
                load_baseline,
            )

            baseline = load_baseline(baseline_path)
            issues = filter_baselined_issues(issues, baseline)

        # Handle --generate-baseline
        generate_baseline_path = options.get("generate_baseline")
        if generate_baseline_path:
            from django_safe_migrations.baseline import generate_baseline

            count = generate_baseline(issues, generate_baseline_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated baseline with {count} issue(s) "
                    f"at {generate_baseline_path}"
                )
            )
            return

        # Interactive mode
        if options.get("interactive"):
            from django_safe_migrations.interactive import review_issues_interactively

            issues = review_issues_interactively(issues)

        # Determine output stream
        output_stream: IO[str]
        if output_file:
            output_stream = open(output_file, "w", encoding="utf-8")
        else:
            output_stream = self.stdout  # type: ignore[assignment]

        try:
            # Get reporter
            reporter_kwargs: dict[str, object] = {"stream": output_stream}
            if output_format == "console":
                reporter_kwargs["show_suggestions"] = show_suggestions

            reporter = get_reporter(output_format, **reporter_kwargs)

            # Generate report
            reporter.report(issues)
        finally:
            # Close file if we opened one
            if output_file:
                output_stream.close()
                self.stdout.write(
                    self.style.SUCCESS(f"Report written to {output_file}")
                )

        # Determine exit code
        errors = [i for i in issues if i.severity == Severity.ERROR]
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        promoted = [i for i in warnings if i.rule_id in warnings_as_errors]

        if errors or promoted:
            sys.exit(1)
        elif warnings and fail_on_warning:
            sys.exit(1)
