"""Deployment-phase classification (``--classify-phase``).

Classifies each migration into a deployment **phase** to support
expand–contract (a.k.a. blue-green / rolling) deploys, where schema changes are
split so old and new application code can run simultaneously:

- **expand** — purely additive, backward-compatible operations (``AddField``,
  ``CreateModel``, ``AddIndex``, ``AddConstraint``). Safe to deploy *before*
  the code that uses them.
- **contract** — destructive or in-place operations that require the old code
  to be gone first (``RemoveField``, ``DeleteModel``, ``Rename*``,
  ``AlterField``, …). Safe to deploy *after* the new code is fully rolled out.
- **data** — data migrations (``RunPython`` / ``RunSQL``).
- **mixed** — a migration that combines more than one of the above. The usual
  advice is to split it so each phase can be deployed independently.
- **empty** — no schema/data operations (e.g. only ``AlterModelOptions``).

This is an *informational* classifier; the phase of an in-place ``AlterField``
is necessarily heuristic (it is treated as ``contract`` — the conservative
"deploy after code" choice).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from django.db.migrations import Migration

logger = logging.getLogger("django_safe_migrations")


class Phase(Enum):
    """A migration's deployment phase."""

    EXPAND = "expand"
    CONTRACT = "contract"
    DATA = "data"
    MIXED = "mixed"
    EMPTY = "empty"


# Operations whose reverse needs no historical state are matched by class name
# to avoid importing django.contrib.postgres (which may pull in psycopg).
_CONCURRENT_EXPAND = {"AddIndexConcurrently"}
_CONCURRENT_CONTRACT = {"RemoveIndexConcurrently"}


def classify_operation(operation: object) -> Optional[str]:
    """Classify a single operation as ``expand`` / ``contract`` / ``data``.

    Args:
        operation: A Django migration operation.

    Returns:
        The category string, or ``None`` for operations that do not affect the
        deployment phase (Python-only model option changes, etc.).
    """
    from django.db.migrations import operations as o

    name = type(operation).__name__
    if name in _CONCURRENT_EXPAND:
        return "expand"
    if name in _CONCURRENT_CONTRACT:
        return "contract"

    if isinstance(operation, (o.AddField, o.CreateModel, o.AddIndex, o.AddConstraint)):
        return "expand"
    if isinstance(
        operation,
        (
            o.RemoveField,
            o.DeleteModel,
            o.RemoveIndex,
            o.RemoveConstraint,
            o.RenameField,
            o.RenameModel,
            o.AlterField,
            o.AlterUniqueTogether,
            o.AlterIndexTogether,
            o.AlterModelTable,
            o.AlterOrderWithRespectTo,
        ),
    ):
        return "contract"
    if isinstance(operation, (o.RunPython, o.RunSQL)):
        return "data"
    return None


def classify_migration(migration: Migration) -> tuple[Phase, dict[str, int]]:
    """Classify a whole migration by aggregating its operations.

    Recurses one level into ``SeparateDatabaseAndState.database_operations`` so
    schema work hidden inside the wrapper is counted.

    Args:
        migration: The Django migration to classify.

    Returns:
        A ``(Phase, counts)`` tuple where ``counts`` maps each category to the
        number of operations in it.
    """
    from django.db import migrations as mig_module

    counts = {"expand": 0, "contract": 0, "data": 0}

    def _tally(op: object) -> None:
        category = classify_operation(op)
        if category is not None:
            counts[category] += 1

    for operation in getattr(migration, "operations", []):
        _tally(operation)
        if isinstance(operation, mig_module.SeparateDatabaseAndState):
            for db_op in operation.database_operations or []:
                _tally(db_op)

    present = {key for key, value in counts.items() if value}
    if not present:
        phase = Phase.EMPTY
    elif present == {"expand"}:
        phase = Phase.EXPAND
    elif present == {"contract"}:
        phase = Phase.CONTRACT
    elif present == {"data"}:
        phase = Phase.DATA
    else:
        phase = Phase.MIXED

    return phase, counts


def classify_all(
    app_labels: Optional[list[str]] = None,
    exclude_apps: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Classify every migration on disk (optionally filtered by app).

    Args:
        app_labels: If given, only classify these apps.
        exclude_apps: App labels to skip.

    Returns:
        A list of ``{app_label, migration_name, phase, counts}`` dicts, sorted
        by app label then migration name.
    """
    from django.db.migrations.loader import MigrationLoader

    exclude = set(exclude_apps or [])
    only = set(app_labels) if app_labels else None

    loader = MigrationLoader(None, ignore_no_migrations=True)
    results: list[dict[str, Any]] = []

    for (app, name), migration in loader.disk_migrations.items():
        if app in exclude:
            continue
        if only is not None and app not in only:
            continue
        phase, counts = classify_migration(migration)
        results.append(
            {
                "app_label": app,
                "migration_name": name,
                "phase": phase.value,
                "counts": counts,
            }
        )

    results.sort(key=lambda r: (r["app_label"], r["migration_name"]))
    logger.debug("Classified %d migration(s)", len(results))
    return results


def render_report(results: list[dict[str, Any]], fmt: str, stream: Any) -> None:
    """Render a classification report.

    Args:
        results: The output of :func:`classify_all`.
        fmt: ``"json"`` for machine-readable output, anything else for a
            console table.
        stream: A writable text stream.
    """
    if fmt == "json":
        import json

        stream.write(json.dumps({"migrations": results}, indent=2) + "\n")
        return

    if not results:
        stream.write("No migrations found to classify.\n")
        return

    app_w = max(len(r["app_label"]) for r in results)
    name_w = max(len(r["migration_name"]) for r in results)
    app_w = max(app_w, len("App"))
    name_w = max(name_w, len("Migration"))

    header = f"{'App':<{app_w}}  {'Migration':<{name_w}}  Phase"
    stream.write(header + "\n")
    stream.write("-" * len(header) + "\n")
    for r in results:
        stream.write(
            f"{r['app_label']:<{app_w}}  "
            f"{r['migration_name']:<{name_w}}  "
            f"{r['phase']}\n"
        )

    # Summary counts by phase.
    summary: dict[str, int] = {}
    for r in results:
        summary[r["phase"]] = summary.get(r["phase"], 0) + 1
    stream.write("\n")
    parts = [f"{phase}: {count}" for phase, count in sorted(summary.items())]
    stream.write("Summary — " + ", ".join(parts) + "\n")
