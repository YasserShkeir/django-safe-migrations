"""Django system check that can block unsafe migrations.

When ``SAFE_MIGRATIONS["BLOCK_UNSAFE"]`` is True, this check reports each
ERROR-level migration issue as a Django ``Error``, which makes commands like
``migrate`` refuse to run while unsafe migrations exist. It is disabled by
default so it never slows normal commands.
"""

from __future__ import annotations

from typing import Any

from django.core.checks import CheckMessage
from django.core.checks import Error as CheckError


def check_migration_safety(
    app_configs: Any = None, **kwargs: Any
) -> list[CheckMessage]:
    """System check that blocks migrate when unsafe migrations exist.

    Returns an empty list unless ``SAFE_MIGRATIONS["BLOCK_UNSAFE"]`` is True.
    """
    from django_safe_migrations.conf import get_block_unsafe

    if not get_block_unsafe():
        return []

    # Import lazily so importing this module never pulls in the analyzer.
    from django_safe_migrations.analyzer import MigrationAnalyzer
    from django_safe_migrations.rules.base import Severity

    try:
        analyzer = MigrationAnalyzer()
        issues = analyzer.analyze_all()
    except Exception:  # noqa: BLE001 - never let the check itself crash commands
        return []

    messages: list[CheckMessage] = []
    for issue in issues:
        if issue.severity is not Severity.ERROR:
            continue
        messages.append(
            CheckError(
                f"Unsafe migration ({issue.rule_id}): {issue.message}",
                hint=issue.suggestion,
                obj=f"{issue.app_label}.{issue.migration_name}",
                id=f"safe_migrations.{issue.rule_id}",
            )
        )
    return messages
