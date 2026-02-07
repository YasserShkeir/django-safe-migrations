"""Migration rules package."""

from __future__ import annotations

import logging

from django_safe_migrations.rules.add_field import (
    AddFieldWithDefaultRule,
    ExpensiveDefaultCallableRule,
    NotNullWithoutDefaultRule,
    PreferBigIntRule,
    PreferIdentityRule,
    PreferTextOverVarcharRule,
    PreferTimestampTZRule,
)
from django_safe_migrations.rules.add_index import (
    ConcurrentInAtomicMigrationRule,
    UnsafeIndexCreationRule,
    UnsafeIndexDeletionRule,
    UnsafeUniqueConstraintRule,
)
from django_safe_migrations.rules.alter_field import (
    AddForeignKeyValidatesRule,
    AlterColumnTypeRule,
    AlterFieldNullFalseRule,
    AlterFieldUniqueRule,
    AlterVarcharLengthRule,
    DropNotNullRule,
    RenameColumnRule,
    RenameModelRule,
)
from django_safe_migrations.rules.base import BaseRule, Issue, Severity
from django_safe_migrations.rules.constraints import (
    AddCheckConstraintRule,
    AddUniqueConstraintRule,
    AlterUniqueTogetherRule,
)
from django_safe_migrations.rules.graph import MissingMergeMigrationRule
from django_safe_migrations.rules.naming import ReservedKeywordColumnRule
from django_safe_migrations.rules.relations import (
    AddManyToManyRule,
    ForeignKeyWithoutIndexRule,
)
from django_safe_migrations.rules.remove_field import (
    DropColumnUnsafeRule,
    DropTableUnsafeRule,
)
from django_safe_migrations.rules.run_sql import (
    EnumAddValueInTransactionRule,
    LargeDataMigrationRule,
    PreferIfExistsRule,
    RequireLockTimeoutRule,
    RunPythonNoBatchingRule,
    RunPythonWithoutReverseRule,
    RunSQLWithoutReverseRule,
    SQLInjectionPatternRule,
)

__all__ = [
    "BaseRule",
    "Issue",
    "Severity",
    # SM001, SM022 - AddField rules
    "NotNullWithoutDefaultRule",
    "ExpensiveDefaultCallableRule",
    # SM002-SM003 - RemoveField rules
    "DropColumnUnsafeRule",
    "DropTableUnsafeRule",
    # SM004-SM006, SM013-SM014, SM020-SM021 - AlterField rules
    "AlterColumnTypeRule",
    "AddForeignKeyValidatesRule",
    "RenameColumnRule",
    "AlterVarcharLengthRule",
    "RenameModelRule",
    "AlterFieldNullFalseRule",
    "AlterFieldUniqueRule",
    # SM007-SM008, SM012, SM016, SM024, SM026 - RunSQL/RunPython rules
    "RunSQLWithoutReverseRule",
    "LargeDataMigrationRule",
    "EnumAddValueInTransactionRule",
    "RunPythonWithoutReverseRule",
    "SQLInjectionPatternRule",
    "RunPythonNoBatchingRule",
    # SM009, SM015, SM017 - Constraint rules
    "AddUniqueConstraintRule",
    "AlterUniqueTogetherRule",
    "AddCheckConstraintRule",
    # SM010-SM011, SM018 - Index rules
    "UnsafeIndexCreationRule",
    "UnsafeUniqueConstraintRule",
    "ConcurrentInAtomicMigrationRule",
    # SM019 - Naming rules
    "ReservedKeywordColumnRule",
    # SM023, SM025 - Relation rules
    "AddManyToManyRule",
    "ForeignKeyWithoutIndexRule",
    # SM027 - Graph rules
    "MissingMergeMigrationRule",
    # SM028-SM036 - v0.5.0 new rules
    "PreferBigIntRule",
    "DropNotNullRule",
    "UnsafeIndexDeletionRule",
    "PreferTextOverVarcharRule",
    "PreferTimestampTZRule",
    "AddFieldWithDefaultRule",
    "PreferIdentityRule",
    "RequireLockTimeoutRule",
    "PreferIfExistsRule",
    # Functions
    "get_all_rules",
    "get_rules_for_db",
    "get_all_rule_ids",
    "get_rule_by_id",
    "clear_extra_rules_cache",
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
    # Index rules (SM010-SM011, SM018)
    UnsafeIndexCreationRule,
    UnsafeUniqueConstraintRule,
    ConcurrentInAtomicMigrationRule,
    # PostgreSQL specific (SM012-SM014)
    EnumAddValueInTransactionRule,
    AlterVarcharLengthRule,
    RenameModelRule,
    # Naming rules (SM019)
    ReservedKeywordColumnRule,
    # v0.4.0 new rules (SM020-SM026)
    AlterFieldNullFalseRule,  # SM020
    AlterFieldUniqueRule,  # SM021
    ExpensiveDefaultCallableRule,  # SM022
    AddManyToManyRule,  # SM023
    SQLInjectionPatternRule,  # SM024
    ForeignKeyWithoutIndexRule,  # SM025
    RunPythonNoBatchingRule,  # SM026
    MissingMergeMigrationRule,  # SM027 (graph-level, check() returns None)
    # v0.5.0 new rules (SM028-SM036)
    PreferBigIntRule,  # SM028
    DropNotNullRule,  # SM029
    UnsafeIndexDeletionRule,  # SM030
    PreferTextOverVarcharRule,  # SM031
    PreferTimestampTZRule,  # SM032
    AddFieldWithDefaultRule,  # SM033
    PreferIdentityRule,  # SM034
    RequireLockTimeoutRule,  # SM035
    PreferIfExistsRule,  # SM036
]

logger = logging.getLogger("django_safe_migrations")

# Cache for loaded extra rules to avoid repeated imports
_extra_rules_cache: list[type[BaseRule]] | None = None


def _load_extra_rules() -> list[type[BaseRule]]:
    """Load custom rules from EXTRA_RULES configuration.

    Uses Django's import_string to dynamically load rule classes.
    Invalid paths are logged as warnings and skipped.

    Returns:
        A list of custom rule classes.
    """
    global _extra_rules_cache

    if _extra_rules_cache is not None:
        return _extra_rules_cache

    from django.utils.module_loading import import_string

    from django_safe_migrations.conf import get_extra_rules

    extra_rule_paths = get_extra_rules()
    loaded_rules: list[type[BaseRule]] = []

    for rule_path in extra_rule_paths:
        try:
            rule_cls = import_string(rule_path)

            # Validate that it's a proper rule class
            if not isinstance(rule_cls, type) or not issubclass(rule_cls, BaseRule):
                logger.warning(
                    "EXTRA_RULES: '%s' is not a subclass of BaseRule, skipping",
                    rule_path,
                )
                continue

            loaded_rules.append(rule_cls)
            logger.debug("Loaded custom rule: %s", rule_path)

        except ImportError as e:
            logger.warning(
                "EXTRA_RULES: Failed to import '%s': %s",
                rule_path,
                e,
            )
        except Exception as e:
            logger.warning(
                "EXTRA_RULES: Error loading '%s': %s",
                rule_path,
                e,
            )

    _extra_rules_cache = loaded_rules
    return loaded_rules


def clear_extra_rules_cache() -> None:
    """Clear the extra rules cache.

    This is useful for testing or when configuration changes.
    """
    global _extra_rules_cache
    _extra_rules_cache = None


def get_all_rules(db_vendor: str = "postgresql") -> list[BaseRule]:
    """Get all rules that apply to the given database vendor.

    This includes both built-in rules and any custom rules configured
    via EXTRA_RULES in settings.

    Args:
        db_vendor: The database vendor (e.g., 'postgresql', 'mysql').

    Returns:
        A list of instantiated rule objects.
    """
    rules = []

    # Load built-in rules
    for rule_cls in ALL_RULES:
        rule = rule_cls()
        if rule.applies_to_db(db_vendor):
            rules.append(rule)

    # Load custom rules from EXTRA_RULES
    for rule_cls in _load_extra_rules():
        try:
            rule = rule_cls()
            if rule.applies_to_db(db_vendor):
                rules.append(rule)
        except Exception as e:
            logger.warning(
                "EXTRA_RULES: Error instantiating '%s': %s",
                rule_cls.__name__,
                e,
            )

    return rules


def get_rules_for_db(db_vendor: str) -> list[BaseRule]:
    """Alias for get_all_rules for clarity.

    Args:
        db_vendor: The database vendor.

    Returns:
        A list of instantiated rule objects.
    """
    return get_all_rules(db_vendor)


def get_all_rule_ids() -> set[str]:
    """Get all known rule IDs.

    This includes both built-in rule IDs and any custom rule IDs
    from EXTRA_RULES configuration.

    Returns:
        A set of all rule IDs (e.g., {"SM001", "SM002", ...}).
    """
    rule_ids = {rule_cls().rule_id for rule_cls in ALL_RULES}

    # Include custom rule IDs
    for rule_cls in _load_extra_rules():
        try:
            rule_ids.add(rule_cls().rule_id)
        except Exception:  # noqa: S110, BLE001  # nosec B110
            pass  # Skip rules that fail to instantiate

    return rule_ids


def get_rule_by_id(rule_id: str) -> type[BaseRule] | None:
    """Get a rule class by its ID.

    Searches both built-in rules and custom rules from EXTRA_RULES.

    Args:
        rule_id: The rule ID (e.g., "SM001").

    Returns:
        The rule class, or None if not found.
    """
    # Check built-in rules first
    for rule_cls in ALL_RULES:
        if rule_cls().rule_id == rule_id:
            return rule_cls

    # Check custom rules
    for rule_cls in _load_extra_rules():
        try:
            if rule_cls().rule_id == rule_id:
                return rule_cls
        except Exception:  # noqa: S110, BLE001  # nosec B110
            pass  # Skip rules that fail to instantiate

    return None
