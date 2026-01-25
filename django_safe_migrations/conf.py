"""Configuration handling for django-safe-migrations.

This module provides a way to configure django-safe-migrations via
Django settings. Add a SAFE_MIGRATIONS dictionary to your settings
to customize behavior.

Example::

    # settings.py
    SAFE_MIGRATIONS = {
        # Disable specific rules
        "DISABLED_RULES": ["SM006", "SM008"],

        # Disable entire categories
        "DISABLED_CATEGORIES": ["reversibility"],

        # Enable only specific categories (whitelist mode)
        # "ENABLED_CATEGORIES": ["destructive", "postgresql"],

        # Change severity levels
        "RULE_SEVERITY": {
            "SM002": "INFO",  # Downgrade to INFO
        },

        # Exclude apps by default
        "EXCLUDED_APPS": ["django_celery_beat", "oauth2_provider"],

        # Fail on warning in addition to errors
        "FAIL_ON_WARNING": False,

        # Per-app rule configuration (overrides global settings)
        "APP_RULES": {
            "legacy_app": {
                "DISABLED_RULES": ["SM001", "SM002"],  # Allow these for legacy
            },
            "new_app": {
                "ENABLED_CATEGORIES": ["high-risk"],  # Only high-risk for new app
            },
        },
    }
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from django_safe_migrations.rules.base import Severity

logger = logging.getLogger("django_safe_migrations")

# Rule categories for grouping related rules
# Each category maps to a list of rule IDs
RULE_CATEGORIES: dict[str, list[str]] = {
    # Database-specific rules
    "postgresql": ["SM005", "SM010", "SM011", "SM012", "SM013", "SM018", "SM021"],
    "mysql": [],  # Currently no MySQL-specific rules
    "sqlite": [],  # Currently no SQLite-specific rules
    # Operation type categories
    "indexes": ["SM010", "SM011", "SM018", "SM021"],
    "constraints": ["SM009", "SM011", "SM015", "SM017", "SM020", "SM021"],
    "destructive": ["SM002", "SM003", "SM009"],
    "relations": ["SM005", "SM023", "SM025"],
    # Safety concern categories
    "locking": ["SM004", "SM005", "SM010", "SM011", "SM013", "SM020", "SM021"],
    "data-loss": ["SM002", "SM003", "SM009"],
    "reversibility": ["SM007", "SM016", "SM017"],
    "data-migrations": ["SM007", "SM008", "SM016", "SM017", "SM022", "SM026"],
    "security": ["SM024"],
    # Severity-based categories
    "high-risk": [
        "SM001",
        "SM002",
        "SM003",
        "SM010",
        "SM011",
        "SM018",
        "SM020",
        "SM021",
        "SM024",
        "SM027",
    ],
    "informational": ["SM006", "SM014", "SM019", "SM023"],
    # Feature categories
    "naming": ["SM019"],
    "schema-changes": [
        "SM001",
        "SM002",
        "SM003",
        "SM004",
        "SM006",
        "SM013",
        "SM014",
        "SM020",
        "SM021",
        "SM023",
    ],
    "performance": ["SM022", "SM025", "SM026"],
}

# Default configuration values
DEFAULTS: dict[str, Any] = {
    "DISABLED_RULES": [],
    "DISABLED_CATEGORIES": [],
    "ENABLED_CATEGORIES": [],  # Empty = all categories enabled
    "RULE_SEVERITY": {},
    "EXCLUDED_APPS": [
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles",
    ],
    "FAIL_ON_WARNING": False,
    "APP_RULES": {},  # Per-app rule configuration
    "EXTRA_RULES": [],  # Custom rule class paths to load
}


def get_config() -> dict[str, Any]:
    """Get the merged configuration from Django settings.

    Returns:
        A dictionary with all configuration values, using defaults
        for any values not specified in settings.
    """
    user_config = getattr(settings, "SAFE_MIGRATIONS", {})

    config = DEFAULTS.copy()
    config.update(user_config)

    return config


def get_disabled_rules() -> list[str]:
    """Get list of disabled rule IDs.

    Returns:
        A list of rule IDs to disable (e.g., ["SM006", "SM008"]).
    """
    config = get_config()
    disabled: list[str] = config.get("DISABLED_RULES", [])
    return disabled


def get_severity_overrides() -> dict[str, Severity]:
    """Get severity overrides for rules.

    Returns:
        A dictionary mapping rule IDs to Severity levels.
    """
    config = get_config()
    raw_overrides = config.get("RULE_SEVERITY", {})

    # Convert string severity names to Severity enum
    overrides: dict[str, Severity] = {}
    for rule_id, severity_str in raw_overrides.items():
        if isinstance(severity_str, str):
            try:
                overrides[rule_id] = Severity(severity_str.lower())
            except ValueError:
                # Try matching by name
                severity_str_upper = severity_str.upper()
                if hasattr(Severity, severity_str_upper):
                    overrides[rule_id] = getattr(Severity, severity_str_upper)
        elif isinstance(severity_str, Severity):
            overrides[rule_id] = severity_str

    return overrides


def get_excluded_apps() -> list[str]:
    """Get list of app labels to exclude from checking.

    Returns:
        A list of app labels to exclude.
    """
    config = get_config()
    excluded: list[str] = config.get("EXCLUDED_APPS", DEFAULTS["EXCLUDED_APPS"])
    return excluded


def get_fail_on_warning() -> bool:
    """Get whether to fail on warnings.

    Returns:
        True if warnings should cause failure, False otherwise.
    """
    config = get_config()
    fail_on_warning: bool = config.get("FAIL_ON_WARNING", False)
    return fail_on_warning


def is_rule_disabled(rule_id: str) -> bool:
    """Check if a specific rule is disabled.

    Args:
        rule_id: The rule ID to check (e.g., "SM001").

    Returns:
        True if the rule is disabled, False otherwise.
    """
    return rule_id in get_disabled_rules()


def get_rule_severity(rule_id: str, default: Severity) -> Severity:
    """Get the severity for a rule, considering overrides.

    Args:
        rule_id: The rule ID to check.
        default: The default severity if no override exists.

    Returns:
        The configured severity for the rule.
    """
    overrides = get_severity_overrides()
    return overrides.get(rule_id, default)


def get_disabled_categories() -> list[str]:
    """Get list of disabled category names.

    Returns:
        A list of category names to disable.
    """
    config = get_config()
    disabled: list[str] = config.get("DISABLED_CATEGORIES", [])
    return disabled


def get_enabled_categories() -> list[str]:
    """Get list of enabled category names (whitelist mode).

    If empty, all categories are enabled (except those in DISABLED_CATEGORIES).

    Returns:
        A list of category names to enable (empty = all enabled).
    """
    config = get_config()
    enabled: list[str] = config.get("ENABLED_CATEGORIES", [])
    return enabled


def get_rules_in_category(category: str) -> list[str]:
    """Get all rule IDs in a category.

    Args:
        category: The category name.

    Returns:
        A list of rule IDs in that category.
    """
    return RULE_CATEGORIES.get(category, [])


def get_all_categories() -> list[str]:
    """Get all available category names.

    Returns:
        A list of all category names.
    """
    return list(RULE_CATEGORIES.keys())


def get_rules_from_categories(categories: list[str]) -> set[str]:
    """Get all rule IDs from multiple categories.

    Args:
        categories: List of category names.

    Returns:
        A set of all rule IDs in those categories.
    """
    rules: set[str] = set()
    for category in categories:
        rules.update(get_rules_in_category(category))
    return rules


def is_rule_disabled_by_category(rule_id: str) -> bool:
    """Check if a rule is disabled via category configuration.

    Logic:
    - If ENABLED_CATEGORIES is set, only rules in those categories are enabled
    - Rules in DISABLED_CATEGORIES are always disabled
    - Individual DISABLED_RULES takes precedence

    Args:
        rule_id: The rule ID to check.

    Returns:
        True if the rule should be disabled, False otherwise.
    """
    enabled_categories = get_enabled_categories()
    disabled_categories = get_disabled_categories()

    # If whitelist mode (ENABLED_CATEGORIES is set)
    if enabled_categories:
        enabled_rules = get_rules_from_categories(enabled_categories)
        if rule_id not in enabled_rules:
            logger.debug(
                "Rule %s disabled: not in enabled categories %s",
                rule_id,
                enabled_categories,
            )
            return True

    # Check if rule is in a disabled category
    if disabled_categories:
        disabled_by_category = get_rules_from_categories(disabled_categories)
        if rule_id in disabled_by_category:
            logger.debug(
                "Rule %s disabled: in disabled categories %s",
                rule_id,
                disabled_categories,
            )
            return True

    return False


def is_rule_enabled(rule_id: str) -> bool:
    """Check if a rule is enabled (considering all disable mechanisms).

    This checks:
    1. Individual DISABLED_RULES
    2. DISABLED_CATEGORIES
    3. ENABLED_CATEGORIES (whitelist mode)

    Args:
        rule_id: The rule ID to check.

    Returns:
        True if the rule should run, False otherwise.
    """
    # Check individual disable first
    if is_rule_disabled(rule_id):
        return False

    # Check category-based disable
    if is_rule_disabled_by_category(rule_id):
        return False

    return True


def get_category_for_rule(rule_id: str) -> list[str]:
    """Get all categories that a rule belongs to.

    Args:
        rule_id: The rule ID to check.

    Returns:
        A list of category names the rule belongs to.
    """
    categories = []
    for category, rules in RULE_CATEGORIES.items():
        if rule_id in rules:
            categories.append(category)
    return categories


# -----------------------------------------------------------------------------
# Per-App Configuration
# -----------------------------------------------------------------------------


def get_app_rules_config() -> dict[str, dict[str, Any]]:
    """Get the per-app rules configuration.

    Returns:
        A dictionary mapping app labels to their rule configurations.
    """
    config = get_config()
    app_rules: dict[str, dict[str, Any]] = config.get("APP_RULES", {})
    return app_rules


def get_app_config(app_label: str) -> dict[str, Any]:
    """Get the rule configuration for a specific app.

    Args:
        app_label: The app label (e.g., 'myapp').

    Returns:
        The app-specific configuration, or empty dict if not configured.
    """
    app_rules = get_app_rules_config()
    return app_rules.get(app_label, {})


def is_rule_enabled_for_app(rule_id: str, app_label: str | None = None) -> bool:
    """Check if a rule is enabled for a specific app.

    This function checks rule enablement with the following precedence:
    1. App-specific DISABLED_RULES
    2. App-specific DISABLED_CATEGORIES / ENABLED_CATEGORIES
    3. Global DISABLED_RULES
    4. Global DISABLED_CATEGORIES / ENABLED_CATEGORIES

    Args:
        rule_id: The rule ID to check.
        app_label: The app label. If None, uses global configuration only.

    Returns:
        True if the rule should run for this app, False otherwise.
    """
    # If no app specified, use global configuration
    if app_label is None:
        return is_rule_enabled(rule_id)

    # Get app-specific configuration
    app_config = get_app_config(app_label)

    # If no app-specific config, fall back to global
    if not app_config:
        return is_rule_enabled(rule_id)

    # Check app-specific DISABLED_RULES first
    app_disabled_rules = app_config.get("DISABLED_RULES", [])
    if rule_id in app_disabled_rules:
        logger.debug(
            "Rule %s disabled for app %s: in app DISABLED_RULES",
            rule_id,
            app_label,
        )
        return False

    # Check app-specific category configuration
    app_enabled_categories = app_config.get("ENABLED_CATEGORIES", [])
    app_disabled_categories = app_config.get("DISABLED_CATEGORIES", [])

    # App-level whitelist mode
    if app_enabled_categories:
        enabled_rules = get_rules_from_categories(app_enabled_categories)
        if rule_id not in enabled_rules:
            logger.debug(
                "Rule %s disabled for app %s: not in app ENABLED_CATEGORIES %s",
                rule_id,
                app_label,
                app_enabled_categories,
            )
            return False

    # App-level disabled categories
    if app_disabled_categories:
        disabled_by_category = get_rules_from_categories(app_disabled_categories)
        if rule_id in disabled_by_category:
            logger.debug(
                "Rule %s disabled for app %s: in app DISABLED_CATEGORIES %s",
                rule_id,
                app_label,
                app_disabled_categories,
            )
            return False

    # If app has any configuration but didn't disable this rule,
    # still check global configuration
    return is_rule_enabled(rule_id)


def get_rule_severity_for_app(
    rule_id: str, default: Severity, app_label: str | None = None
) -> Severity:
    """Get the severity for a rule, considering app-specific overrides.

    Args:
        rule_id: The rule ID to check.
        default: The default severity if no override exists.
        app_label: The app label. If None, uses global configuration only.

    Returns:
        The configured severity for the rule.
    """
    # Check app-specific severity first
    if app_label:
        app_config = get_app_config(app_label)
        app_severity = app_config.get("RULE_SEVERITY", {})
        if rule_id in app_severity:
            severity_str = app_severity[rule_id]
            if isinstance(severity_str, str):
                try:
                    return Severity(severity_str.lower())
                except ValueError:
                    if hasattr(Severity, severity_str.upper()):
                        result = getattr(Severity, severity_str.upper())
                        if isinstance(result, Severity):
                            return result
            elif isinstance(severity_str, Severity):
                return severity_str

    # Fall back to global severity
    return get_rule_severity(rule_id, default)


# -----------------------------------------------------------------------------
# Configuration Validation
# -----------------------------------------------------------------------------


def _string_similarity(s1: str, s2: str) -> float:
    """Calculate simple string similarity ratio.

    Uses a basic algorithm comparing character overlap.
    Returns a value between 0 (no similarity) and 1 (identical).
    """
    if not s1 or not s2:
        return 0.0
    s1_lower = s1.lower()
    s2_lower = s2.lower()
    if s1_lower == s2_lower:
        return 1.0

    # Check for prefix match
    min_len = min(len(s1_lower), len(s2_lower))
    prefix_match = 0
    for i in range(min_len):
        if s1_lower[i] == s2_lower[i]:
            prefix_match += 1
        else:
            break

    # Simple character overlap ratio
    set1 = set(s1_lower)
    set2 = set(s2_lower)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    overlap_ratio = intersection / union if union else 0
    prefix_ratio = prefix_match / max(len(s1_lower), len(s2_lower))

    return (overlap_ratio + prefix_ratio) / 2


def _find_similar(
    name: str, valid_names: set[str], threshold: float = 0.5
) -> str | None:
    """Find the most similar valid name if above threshold.

    Args:
        name: The potentially invalid name.
        valid_names: Set of valid names to compare against.
        threshold: Minimum similarity score to suggest (0-1).

    Returns:
        The most similar valid name, or None if none above threshold.
    """
    best_match = None
    best_score = threshold

    for valid_name in valid_names:
        score = _string_similarity(name, valid_name)
        if score > best_score:
            best_score = score
            best_match = valid_name

    return best_match


def validate_config() -> list[str]:
    """Validate the SAFE_MIGRATIONS configuration.

    Checks for:
    - Invalid rule IDs in DISABLED_RULES
    - Invalid category names in DISABLED_CATEGORIES and ENABLED_CATEGORIES
    - Invalid rule IDs in RULE_SEVERITY
    - Invalid app configurations in APP_RULES

    Returns:
        A list of warning messages for any invalid configuration values.
        Empty list if configuration is valid.
    """
    # Import here to avoid circular import
    from django_safe_migrations.rules import get_all_rule_ids

    warnings: list[str] = []
    config = get_config()

    valid_rule_ids = get_all_rule_ids()
    valid_categories = set(RULE_CATEGORIES.keys())

    # Validate global DISABLED_RULES
    for rule_id in config.get("DISABLED_RULES", []):
        if rule_id not in valid_rule_ids:
            suggestion = _find_similar(rule_id, valid_rule_ids)
            msg = f"Unknown rule ID in DISABLED_RULES: '{rule_id}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(msg)

    # Validate global DISABLED_CATEGORIES
    for category in config.get("DISABLED_CATEGORIES", []):
        if category not in valid_categories:
            suggestion = _find_similar(category, valid_categories)
            msg = f"Unknown category in DISABLED_CATEGORIES: '{category}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(msg)

    # Validate global ENABLED_CATEGORIES
    for category in config.get("ENABLED_CATEGORIES", []):
        if category not in valid_categories:
            suggestion = _find_similar(category, valid_categories)
            msg = f"Unknown category in ENABLED_CATEGORIES: '{category}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(msg)

    # Validate global RULE_SEVERITY
    for rule_id in config.get("RULE_SEVERITY", {}).keys():
        if rule_id not in valid_rule_ids:
            suggestion = _find_similar(rule_id, valid_rule_ids)
            msg = f"Unknown rule ID in RULE_SEVERITY: '{rule_id}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(msg)

    # Validate APP_RULES
    for app_label, app_config in config.get("APP_RULES", {}).items():
        if not isinstance(app_config, dict):
            warnings.append(
                f"APP_RULES['{app_label}'] should be a dictionary, "
                f"got {type(app_config).__name__}"
            )
            continue

        # Validate app-specific DISABLED_RULES
        for rule_id in app_config.get("DISABLED_RULES", []):
            if rule_id not in valid_rule_ids:
                suggestion = _find_similar(rule_id, valid_rule_ids)
                msg = (
                    f"Unknown rule ID in APP_RULES['{app_label}']"
                    f"['DISABLED_RULES']: '{rule_id}'"
                )
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                warnings.append(msg)

        # Validate app-specific DISABLED_CATEGORIES
        for category in app_config.get("DISABLED_CATEGORIES", []):
            if category not in valid_categories:
                suggestion = _find_similar(category, valid_categories)
                msg = (
                    f"Unknown category in APP_RULES['{app_label}']"
                    f"['DISABLED_CATEGORIES']: '{category}'"
                )
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                warnings.append(msg)

        # Validate app-specific ENABLED_CATEGORIES
        for category in app_config.get("ENABLED_CATEGORIES", []):
            if category not in valid_categories:
                suggestion = _find_similar(category, valid_categories)
                msg = (
                    f"Unknown category in APP_RULES['{app_label}']"
                    f"['ENABLED_CATEGORIES']: '{category}'"
                )
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                warnings.append(msg)

        # Validate app-specific RULE_SEVERITY
        for rule_id in app_config.get("RULE_SEVERITY", {}).keys():
            if rule_id not in valid_rule_ids:
                suggestion = _find_similar(rule_id, valid_rule_ids)
                msg = (
                    f"Unknown rule ID in APP_RULES['{app_label}']"
                    f"['RULE_SEVERITY']: '{rule_id}'"
                )
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                warnings.append(msg)

    return warnings


def log_config_warnings() -> None:
    """Validate configuration and log any warnings.

    This function should be called during startup to alert users
    of configuration issues.
    """
    warnings = validate_config()
    for warning in warnings:
        logger.warning("Configuration warning: %s", warning)


# -----------------------------------------------------------------------------
# Custom Rule Plugin System
# -----------------------------------------------------------------------------


def get_extra_rules() -> list[str]:
    """Get extra rule class paths from configuration.

    Returns:
        A list of dotted paths to custom rule classes.
        Example: ["myproject.rules.CustomRule", "another.module.MyRule"]
    """
    config = get_config()
    extra_rules: list[str] = config.get("EXTRA_RULES", [])
    return extra_rules
