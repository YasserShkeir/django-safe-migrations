"""``makemigrations`` wrapper that lints newly generated migrations.

Subclasses Django's ``makemigrations`` so that, after migrations are created,
they are analysed for safety issues. By default it only *warns* (it never
blocks creating a migration); pass ``--lint-strict`` to exit non-zero when the
new migrations contain ERROR-level issues. Use ``--no-lint`` to skip linting.

The linting is wrapped so it can never break ``makemigrations`` itself.
"""

from __future__ import annotations

import sys
from typing import Any

from django.core.management.commands.makemigrations import Command as BaseCommand


class Command(BaseCommand):
    """``makemigrations`` with a post-generation safety lint."""

    def add_arguments(self, parser: Any) -> None:
        """Add the lint-control arguments on top of makemigrations'."""
        super().add_arguments(parser)
        parser.add_argument(
            "--no-lint",
            action="store_true",
            help="Skip safe-migrations linting after generating migrations",
        )
        parser.add_argument(
            "--lint-strict",
            action="store_true",
            help="Exit non-zero if newly created migrations have ERROR issues",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Generate migrations, then lint them (warn-only by default)."""
        super().handle(*args, **options)

        if (
            options.get("no_lint")
            or options.get("dry_run")
            or options.get("check_changes")
        ):
            return

        self._lint_migrations(strict=bool(options.get("lint_strict")))

    def _lint_migrations(self, strict: bool) -> None:
        """Analyse migrations and report issues; optionally exit non-zero."""
        try:
            from django_safe_migrations.analyzer import MigrationAnalyzer
            from django_safe_migrations.rules.base import Severity

            analyzer = MigrationAnalyzer()
            try:
                issues = analyzer.analyze_new_migrations()
            except Exception:  # noqa: BLE001 - no DB / unapplied lookup failed
                issues = analyzer.analyze_all()
        except Exception:  # noqa: BLE001 - never let linting break makemigrations
            return

        if not issues:
            return

        self.stdout.write(self.style.WARNING("\nMigration safety issues detected:"))
        for issue in issues:
            self.stdout.write(f"  {issue}")

        errors = [i for i in issues if i.severity is Severity.ERROR]
        if errors and strict:
            self.stderr.write(
                self.style.ERROR(
                    f"\n{len(errors)} unsafe migration issue(s). "
                    "Fix them, or re-run without --lint-strict."
                )
            )
            sys.exit(1)
