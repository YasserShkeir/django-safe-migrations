"""Management command to check migrations for unsafe operations."""

from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.reporters import get_reporter
from django_safe_migrations.rules.base import Severity


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
            choices=["console", "json", "github"],
            default="console",
            help="Output format (default: console)",
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

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command.

        Args:
            *args: Positional arguments.
            **options: Command options.
        """
        app_labels = options["app_labels"]
        output_format = options["format"]
        fail_on_warning = options["fail_on_warning"]
        new_only = options["new_only"]
        show_suggestions = not options["no_suggestions"]
        exclude_apps = options["exclude_apps"]
        include_django_apps = options["include_django_apps"]

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
        analyzer = MigrationAnalyzer()

        # Collect issues
        issues = []

        if new_only:
            # Only check unapplied migrations
            if app_labels:
                for app_label in app_labels:
                    issues.extend(analyzer.analyze_new_migrations(app_label))
            else:
                issues.extend(analyzer.analyze_new_migrations())
        elif app_labels:
            # Check specific apps
            for app_label in app_labels:
                if app_label not in exclude_apps:
                    issues.extend(analyzer.analyze_app(app_label))
        else:
            # Check all apps
            issues.extend(analyzer.analyze_all(exclude_apps=exclude_apps))

        # Get reporter
        reporter_kwargs: dict[str, object] = {"stream": self.stdout}
        if output_format == "console":
            reporter_kwargs["show_suggestions"] = show_suggestions

        reporter = get_reporter(output_format, **reporter_kwargs)

        # Generate report
        reporter.report(issues)

        # Determine exit code
        errors = [i for i in issues if i.severity == Severity.ERROR]
        warnings = [i for i in issues if i.severity == Severity.WARNING]

        if errors:
            sys.exit(1)
        elif warnings and fail_on_warning:
            sys.exit(1)
