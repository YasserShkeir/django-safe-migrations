"""Reverse-migration safety checks (``--check-reverse``).

A migration can be perfectly *reversible* (Django can generate the backwards
operations) yet have a rollback path that is itself **dangerous in
production**. Rolling back an additive migration runs the destructive inverse:

- a forward ``AddField`` reverses to ``DROP COLUMN`` (data loss),
- a forward ``CreateModel`` reverses to ``DROP TABLE`` (data loss),
- a forward ``AddIndex`` reverses to ``DROP INDEX`` (a brief lock),
- a forward ``AddConstraint`` reverses to ``DROP CONSTRAINT``.

These checks are **distinct** from SM007 / SM016, which flag ``RunSQL`` /
``RunPython`` that cannot be reversed *at all*. They run only when the user
opts in with ``--check-reverse`` and emit issues under the ``RV0xx`` family so
they are never confused with the forward (``SM0xx``) rules.

Scope: only operations whose reverse is unambiguous **without reconstructing
lost state** are reported. Reverses that need historical state (``RemoveField``
re-adding a column, ``DeleteModel`` recreating a table, ``AlterField``
restoring the old field) are intentionally out of scope to avoid guessing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django_safe_migrations.rules.base import Issue, Severity

if TYPE_CHECKING:
    from django.db.migrations import Migration

logger = logging.getLogger("django_safe_migrations")


def _check_operation_reverse(operation: object) -> Optional[Issue]:
    """Return a reverse-safety Issue for one operation, or None.

    Args:
        operation: A Django migration operation.

    Returns:
        An :class:`Issue` describing the danger on rollback, else ``None``.
    """
    from django.db import migrations
    from django.db.migrations import operations as ops

    # AddField -> reverse drops the column (and its data).
    if isinstance(operation, ops.AddField):
        model = getattr(operation, "model_name", "?")
        name = getattr(operation, "name", "?")
        return Issue(
            rule_id="RV001",
            severity=Severity.WARNING,
            operation=f"AddField({model}.{name})",
            message=(
                f"Rolling back this migration drops column "
                f"'{model}.{name}' — any data written to it since deploy "
                f"is lost."
            ),
            suggestion=(
                "If the rollback path matters, split the change so the column "
                "is removed in a later, separate migration, or accept that a "
                "rollback is destructive and document it."
            ),
        )

    # CreateModel -> reverse drops the whole table.
    if isinstance(operation, ops.CreateModel):
        model = getattr(operation, "name", "?")
        return Issue(
            rule_id="RV002",
            severity=Severity.WARNING,
            operation=f"CreateModel({model})",
            message=(
                f"Rolling back this migration drops the table for model "
                f"'{model}' and all of its rows."
            ),
            suggestion=(
                "Rolling back a CreateModel is destructive by nature. Make "
                "sure the rollback is intentional and the data is expendable "
                "(or backed up) before relying on it."
            ),
        )

    # AddIndex -> reverse drops the index (briefly locks the table).
    if isinstance(operation, ops.AddIndex):
        model = getattr(operation, "model_name", "?")
        index = getattr(operation, "index", None)
        index_name = getattr(index, "name", "?")
        return Issue(
            rule_id="RV003",
            severity=Severity.INFO,
            operation=f"AddIndex({model}.{index_name})",
            message=(
                f"Rolling back this migration drops index '{index_name}'. "
                f"DROP INDEX takes a brief exclusive lock; on a large table "
                f"this can stall queries during the rollback."
            ),
            suggestion=(
                "On PostgreSQL, reverse a concurrently-created index with "
                "DROP INDEX CONCURRENTLY (via a hand-written RunSQL reverse) "
                "to avoid the lock."
            ),
        )

    # AddConstraint -> reverse drops the constraint.
    if isinstance(operation, ops.AddConstraint):
        model = getattr(operation, "model_name", "?")
        constraint = getattr(operation, "constraint", None)
        constraint_name = getattr(constraint, "name", "?")
        return Issue(
            rule_id="RV004",
            severity=Severity.INFO,
            operation=f"AddConstraint({model}.{constraint_name})",
            message=(
                f"Rolling back this migration drops constraint "
                f"'{constraint_name}' on '{model}', removing the integrity "
                f"guarantee it enforced."
            ),
            suggestion=(
                "Confirm that dropping this constraint on rollback is "
                "acceptable for your data integrity requirements."
            ),
        )

    # Silence the unused import when none of the branches matched.
    del migrations
    return None


def analyze_reverse_safety(
    migration: Migration,
    app_label: Optional[str] = None,
    migration_name: Optional[str] = None,
    file_path: Optional[str] = None,
) -> list[Issue]:
    """Analyse a migration's **rollback** path for dangerous operations.

    Args:
        migration: The Django migration to analyse.
        app_label: The app label (for issue enrichment).
        migration_name: The migration name (for issue enrichment).
        file_path: The migration file path (for issue enrichment).

    Returns:
        A list of ``RV0xx`` issues describing rollback dangers.
    """
    issues: list[Issue] = []
    operations = getattr(migration, "operations", [])

    for idx, operation in enumerate(operations):
        issue = _check_operation_reverse(operation)
        if issue is None:
            continue
        issue.app_label = app_label
        issue.migration_name = migration_name
        issue.file_path = file_path
        issue.operation_index = idx
        issues.append(issue)

    logger.debug(
        "Reverse analysis of %s.%s: %d rollback issue(s)",
        app_label,
        migration_name,
        len(issues),
    )
    return issues
