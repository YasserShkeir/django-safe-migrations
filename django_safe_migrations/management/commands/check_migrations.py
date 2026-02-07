"""Management command to check migrations for unsafe operations."""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from django.core.management.base import BaseCommand, CommandParser

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.conf import get_category_for_rule, log_config_warnings
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
        fail_on_warning = options["fail_on_warning"]
        new_only = options["new_only"]
        show_suggestions = not options["no_suggestions"]
        exclude_apps = options["exclude_apps"]
        include_django_apps = options["include_django_apps"]
        verbose = options.get("verbose", False)

        # Build exclude list
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
        analyzer = MigrationAnalyzer(verbose=verbose)

        # Collect issues
        issues: list[Issue] = []

        diff_ref = options.get("diff")
        if diff_ref is not None:
            from django_safe_migrations.diff import get_changed_apps_and_migrations

            changed = get_changed_apps_and_migrations(diff_ref)
            if verbose:
                self.stderr.write(
                    f"Diff mode: checking {len(changed)} changed migration(s)"
                )
            for app_label, migration_name in changed:
                if app_label not in exclude_apps:
                    app_issues = analyzer.analyze_app(app_label)
                    issues.extend(
                        i for i in app_issues if i.migration_name == migration_name
                    )
        elif new_only:
            if app_labels:
                for app_label in app_labels:
                    issues.extend(analyzer.analyze_new_migrations(app_label))
            else:
                issues.extend(analyzer.analyze_new_migrations())
        elif app_labels:
            for app_label in app_labels:
                if app_label not in exclude_apps:
                    issues.extend(analyzer.analyze_app(app_label))
        else:
            issues.extend(analyzer.analyze_all(exclude_apps=exclude_apps))

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

        if errors:
            sys.exit(1)
        elif warnings and fail_on_warning:
            sys.exit(1)
