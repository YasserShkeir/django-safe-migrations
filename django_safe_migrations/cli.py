"""Command-line interface for django-safe-migrations.

This module provides a standalone CLI that can be used with pre-commit
without requiring Django's manage.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def setup_django() -> bool:
    """Configure Django settings for standalone CLI usage.

    Returns:
        True if Django was set up successfully, False otherwise.
    """
    # Try to configure Django
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")

    if not settings_module:
        # Try common settings module names
        for candidate in ["settings", "config.settings", "project.settings"]:
            try:
                os.environ["DJANGO_SETTINGS_MODULE"] = candidate
                import django

                django.setup()
                return True
            except Exception:  # noqa: S110, BLE001  # nosec B112
                # Continue trying other candidates
                continue

        # Reset if none worked
        if "DJANGO_SETTINGS_MODULE" in os.environ:
            del os.environ["DJANGO_SETTINGS_MODULE"]
        return False

    try:
        import django

        django.setup()
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    """Run the migration checker CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Exit code (0 for success, 1 for issues found).
    """
    parser = argparse.ArgumentParser(
        description="Check Django migrations for unsafe operations",
        prog="django-safe-migrations",
    )
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

    args: Namespace = parser.parse_args(argv)

    # Setup Django
    if not setup_django():
        print(
            "Error: Could not configure Django. "
            "Please set DJANGO_SETTINGS_MODULE environment variable.",
            file=sys.stderr,
        )
        return 1

    # Import after Django setup
    from django_safe_migrations.analyzer import MigrationAnalyzer
    from django_safe_migrations.reporters import get_reporter
    from django_safe_migrations.rules.base import Severity

    # Build exclude list
    exclude_apps = list(args.exclude_apps)
    if not args.include_django_apps:
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

    if args.new_only:
        if args.app_labels:
            for app_label in args.app_labels:
                issues.extend(analyzer.analyze_new_migrations(app_label))
        else:
            issues.extend(analyzer.analyze_new_migrations())
    elif args.app_labels:
        for app_label in args.app_labels:
            if app_label not in exclude_apps:
                issues.extend(analyzer.analyze_app(app_label))
    else:
        issues.extend(analyzer.analyze_all(exclude_apps=exclude_apps))

    # Get reporter
    reporter_kwargs: dict[str, object] = {"stream": sys.stdout}
    if args.format == "console":
        reporter_kwargs["show_suggestions"] = not args.no_suggestions

    reporter = get_reporter(args.format, **reporter_kwargs)

    # Generate report
    reporter.report(issues)

    # Determine exit code
    errors = [i for i in issues if i.severity == Severity.ERROR]
    warnings = [i for i in issues if i.severity == Severity.WARNING]

    if errors:
        return 1
    elif warnings and args.fail_on_warning:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
