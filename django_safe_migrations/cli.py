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


def list_rules(output_format: str = "console") -> int:
    """List all available rules.

    Lists both built-in rules and any custom rules configured via EXTRA_RULES.

    Args:
        output_format: Output format ('console' or 'json').

    Returns:
        Exit code (always 0).
    """
    import json as json_module

    from django_safe_migrations.conf import get_category_for_rule
    from django_safe_migrations.rules import ALL_RULES, _load_extra_rules

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
        print(json_module.dumps(rules_data, indent=2))
    else:
        # Console table format
        print("Available Rules:")
        print("-" * 80)
        for rule_info in rules_data:
            severity_str = str(rule_info["severity"]).upper()
            categories_str = ", ".join(rule_info["categories"]) or "none"
            db_str = ", ".join(rule_info["db_vendors"])
            print(f"{rule_info['rule_id']} [{severity_str}] {rule_info['description']}")
            print(f"    Categories: {categories_str}")
            print(f"    Databases: {db_str}")
            print()

    return 0


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
        epilog="""
Examples:
  %(prog)s                      Check all migrations
  %(prog)s myapp                Check specific app
  %(prog)s --new-only           Check unapplied migrations only
  %(prog)s --format=json        Output as JSON
  %(prog)s --format=gitlab      GitLab Code Quality output
  %(prog)s --list-rules         Show all available rules
  %(prog)s --interactive        Review issues one-by-one
  %(prog)s --diff               Only check changed migrations
  %(prog)s --baseline base.json Exclude baselined issues

Documentation: https://django-safe-migrations.readthedocs.io/
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        "--list-rules",
        action="store_true",
        help="List all available rules and exit",
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
        "--verbose",
        "-v",
        action="store_true",
        help="Show progress information during analysis",
    )
    parser.add_argument(
        "--interactive",
        "-i",
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

    args: Namespace = parser.parse_args(argv)

    # Handle --list-rules before Django setup (doesn't need full Django)
    if args.list_rules:
        return list_rules(args.format)

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
    from django_safe_migrations.conf import log_config_warnings
    from django_safe_migrations.reporters import get_reporter
    from django_safe_migrations.rules.base import Issue, Severity

    # Validate configuration and log any warnings
    log_config_warnings()

    # Handle --watch mode
    if args.watch:
        from django_safe_migrations.watch import watch_migrations

        watch_migrations()
        return 0

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
    analyzer = MigrationAnalyzer(verbose=args.verbose)

    # Collect issues
    issues: list[Issue] = []

    if args.diff is not None:
        # Diff mode — only check changed migrations
        from django_safe_migrations.diff import get_changed_apps_and_migrations

        changed = get_changed_apps_and_migrations(args.diff)
        if args.verbose:
            print(
                f"Diff mode: checking {len(changed)} changed migration(s)",
                file=sys.stderr,
            )
        for app_label, migration_name in changed:
            if app_label not in exclude_apps:
                app_issues = analyzer.analyze_app(app_label)
                # Filter to only the changed migration
                issues.extend(
                    i for i in app_issues if i.migration_name == migration_name
                )
    elif args.new_only:
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

    # Apply baseline filtering
    if args.baseline:
        from django_safe_migrations.baseline import (
            filter_baselined_issues,
            load_baseline,
        )

        baseline = load_baseline(args.baseline)
        issues = filter_baselined_issues(issues, baseline)

    # Handle --generate-baseline
    if args.generate_baseline:
        from django_safe_migrations.baseline import generate_baseline

        count = generate_baseline(issues, args.generate_baseline)
        print(f"Generated baseline with {count} issue(s) at {args.generate_baseline}")
        return 0

    # Interactive mode
    if args.interactive:
        from django_safe_migrations.interactive import review_issues_interactively

        issues = review_issues_interactively(issues)

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
