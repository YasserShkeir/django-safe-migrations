"""Migration rules package."""

from __future__ import annotations

from django_safe_migrations.rules.add_field import NotNullWithoutDefaultRule
from django_safe_migrations.rules.add_index import (
    UnsafeIndexCreationRule,
    UnsafeUniqueConstraintRule,
)
from django_safe_migrations.rules.alter_field import (
    AddForeignKeyValidatesRule,
    AlterColumnTypeRule,
    AlterVarcharLengthRule,
    RenameColumnRule,
    RenameModelRule,
)
from django_safe_migrations.rules.base import BaseRule, Issue, Severity
from django_safe_migrations.rules.constraints import (
    AddCheckConstraintRule,
    AddUniqueConstraintRule,
    AlterUniqueTogetherRule,
)
from django_safe_migrations.rules.remove_field import (
    DropColumnUnsafeRule,
    DropTableUnsafeRule,
)
from django_safe_migrations.rules.run_sql import (
    EnumAddValueInTransactionRule,
    LargeDataMigrationRule,
    RunPythonWithoutReverseRule,
    RunSQLWithoutReverseRule,
)

__all__ = [
    "BaseRule",
    "Issue",
    "Severity",
    # SM001 - AddField rules
    "NotNullWithoutDefaultRule",
    # SM002-SM003 - RemoveField rules
    "DropColumnUnsafeRule",
    "DropTableUnsafeRule",
    # SM004-SM006, SM013-SM014 - AlterField rules
    "AlterColumnTypeRule",
    "AddForeignKeyValidatesRule",
    "RenameColumnRule",
    "AlterVarcharLengthRule",
    "RenameModelRule",
    # SM007-SM008, SM012, SM016 - RunSQL/RunPython rules
    "RunSQLWithoutReverseRule",
    "LargeDataMigrationRule",
    "EnumAddValueInTransactionRule",
    "RunPythonWithoutReverseRule",
    # SM009, SM015, SM017 - Constraint rules
    "AddUniqueConstraintRule",
    "AlterUniqueTogetherRule",
    "AddCheckConstraintRule",
    # SM010-SM011 - Index rules
    "UnsafeIndexCreationRule",
    "UnsafeUniqueConstraintRule",
    # Functions
    "get_all_rules",
    "get_rules_for_db",
]

# Registry of all available rules
ALL_RULES: list[type[BaseRule]] = [
    # High priority (SM001-SM003)
    NotNullWithoutDefaultRule,
    DropColumnUnsafeRule,
    DropTableUnsafeRule,
    # Medium priority (SM004-SM006)
    AlterColumnTypeRule,
    AddForeignKeyValidatesRule,
    RenameColumnRule,
    # RunSQL/RunPython (SM007-SM008, SM016)
    RunSQLWithoutReverseRule,
    LargeDataMigrationRule,
    RunPythonWithoutReverseRule,
    # Constraint rules (SM009, SM015, SM017)
    AddUniqueConstraintRule,
    AlterUniqueTogetherRule,
    AddCheckConstraintRule,
    # Index rules (SM010-SM011)
    UnsafeIndexCreationRule,
    UnsafeUniqueConstraintRule,
    # PostgreSQL specific (SM012-SM014)
    EnumAddValueInTransactionRule,
    AlterVarcharLengthRule,
    RenameModelRule,
]


def get_all_rules(db_vendor: str = "postgresql") -> list[BaseRule]:
    """Get all rules that apply to the given database vendor.

    Args:
        db_vendor: The database vendor (e.g., 'postgresql', 'mysql').

    Returns:
        A list of instantiated rule objects.
    """
    rules = []
    for rule_cls in ALL_RULES:
        rule = rule_cls()
        if rule.applies_to_db(db_vendor):
            rules.append(rule)
    return rules


def get_rules_for_db(db_vendor: str) -> list[BaseRule]:
    """Alias for get_all_rules for clarity.

    Args:
        db_vendor: The database vendor.

    Returns:
        A list of instantiated rule objects.
    """
    return get_all_rules(db_vendor)
