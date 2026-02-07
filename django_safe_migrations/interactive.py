"""Interactive mode for reviewing migration issues one-by-one."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue


def review_issues_interactively(issues: list[Issue]) -> list[Issue]:
    """Interactively review each issue and let the user decide the action.

    For each issue, the user can:
    - [s] Skip (suppress) the issue
    - [f] Show the fix suggestion
    - [k] Keep the issue in the report
    - [q] Quit interactive mode and keep remaining issues

    Args:
        issues: List of issues to review.

    Returns:
        Filtered list of issues the user chose to keep.
    """
    if not issues:
        return issues

    kept: list[Issue] = []
    total = len(issues)

    print(f"\nInteractive mode: {total} issue(s) to review\n", file=sys.stderr)

    for idx, issue in enumerate(issues, 1):
        print(
            f"[{idx}/{total}] {issue.rule_id} [{issue.severity.value.upper()}]",
            file=sys.stderr,
        )
        if issue.app_label and issue.migration_name:
            print(
                f"  Migration: {issue.app_label}.{issue.migration_name}",
                file=sys.stderr,
            )
        if issue.file_path:
            loc = issue.file_path
            if issue.line_number:
                loc += f":{issue.line_number}"
            print(f"  Location: {loc}", file=sys.stderr)
        print(f"  {issue.message}", file=sys.stderr)
        print(file=sys.stderr)

        while True:
            try:
                choice = (
                    input("  [k]eep / [s]kip / [f]ix suggestion / [q]uit: ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                print("\nKeeping remaining issues.", file=sys.stderr)
                kept.extend(issues[idx - 1 :])
                return kept

            if choice == "k":
                kept.append(issue)
                break
            elif choice == "s":
                if issue.file_path and issue.line_number:
                    print(
                        f"  Tip: Add '# safe-migrations: ignore {issue.rule_id}' "
                        "to suppress permanently.",
                        file=sys.stderr,
                    )
                break
            elif choice == "f":
                if issue.suggestion:
                    print(f"\n{issue.suggestion}\n", file=sys.stderr)
                else:
                    print("  No suggestion available.", file=sys.stderr)
                # Don't break — let user choose k/s/q after seeing suggestion
            elif choice == "q":
                kept.extend(issues[idx - 1 :])
                return kept
            else:
                print("  Invalid choice. Use k, s, f, or q.", file=sys.stderr)

    return kept
