"""Rules for migration graph analysis (app-level checks)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import migrations

from django_safe_migrations.rules.base import BaseRule, Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations.operations.base import Operation


class MissingMergeMigrationRule(BaseRule):
    """Detect apps with multiple leaf migrations that need a merge.

    When multiple branches are merged in version control, each branch
    may have created migrations that depend on the same parent. This
    results in multiple "leaf" migrations, which Django cannot apply
    without a merge migration.

    This is a graph-level check, not an operation-level check.
    The ``check()`` method always returns None; use ``check_graph()``
    for the actual detection.
    """

    rule_id = "SM027"
    severity = Severity.ERROR
    description = "Multiple leaf migrations require a merge migration"

    def check(
        self,
        operation: Operation,
        migration: migrations.Migration,
        **kwargs: object,
    ) -> Optional[Issue]:
        """Operation-level check — always returns None.

        SM027 is a graph-level check, not an operation-level check.

        Args:
            operation: The migration operation (unused).
            migration: The migration (unused).
            **kwargs: Additional context (unused).

        Returns:
            Always None.
        """
        return None

    @classmethod
    def check_graph(
        cls,
        app_label: str,
        leaf_migrations: list[str],
    ) -> Issue | None:
        """Check if an app has multiple leaf migrations requiring a merge.

        Args:
            app_label: The app label being checked.
            leaf_migrations: List of leaf migration names for the app.

        Returns:
            An Issue if multiple leaf migrations exist, None otherwise.
        """
        if len(leaf_migrations) <= 1:
            return None

        migration_list = ", ".join(sorted(leaf_migrations))

        return Issue(
            rule_id=cls.rule_id,
            severity=cls.severity,
            operation=f"Multiple leaf migrations in {app_label}",
            message=(
                f"App '{app_label}' has {len(leaf_migrations)} leaf migrations: "
                f"{migration_list}. Create a merge migration with: "
                f"python manage.py makemigrations --merge {app_label}"
            ),
            suggestion=get_merge_suggestion(app_label, leaf_migrations),
            app_label=app_label,
            migration_name=None,
            file_path=None,
            line_number=None,
        )

    def get_suggestion(self, operation: Operation) -> str:
        """Return generic suggestion for merge migrations.

        Args:
            operation: The migration operation (unused).

        Returns:
            A suggestion string.
        """
        return (
            "Run: python manage.py makemigrations --merge <app_label>\n"
            "This creates a merge migration resolving the branch conflict."
        )


def get_merge_suggestion(app_label: str, leaf_migrations: list[str]) -> str:
    """Generate suggestion for creating merge migration.

    Args:
        app_label: The app label.
        leaf_migrations: List of leaf migration names.

    Returns:
        A multi-line string with the suggested fix.
    """
    migrations_str = "\n        ".join(
        f'("{app_label}", "{m}"),' for m in sorted(leaf_migrations)
    )

    return f"""Create a merge migration to resolve the conflict:

1. Automatic (recommended):
   python manage.py makemigrations --merge {app_label}

   Django will create a migration like:
   class Migration(migrations.Migration):
       dependencies = [
        {migrations_str}
       ]
       operations = []

2. Manual (if auto-merge fails):
   Create a new migration file in {app_label}/migrations/ with:

   from django.db import migrations

   class Migration(migrations.Migration):
       dependencies = [
        {migrations_str}
       ]

       # Empty operations - this just merges the branches
       operations = []

3. Prevention:
   - Coordinate migration creation across branches
   - Rebase feature branches frequently
   - Consider using migration locking in CI
"""
