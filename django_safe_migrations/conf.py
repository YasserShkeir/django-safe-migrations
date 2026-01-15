"""Configuration handling for django-safe-migrations.

This module provides a way to configure django-safe-migrations via
Django settings. Add a SAFE_MIGRATIONS dictionary to your settings
to customize behavior.

Example::

    # settings.py
    SAFE_MIGRATIONS = {
        # Disable specific rules
        "DISABLED_RULES": ["SM006", "SM008"],

        # Change severity levels
        "RULE_SEVERITY": {
            "SM002": "INFO",  # Downgrade to INFO
        },

        # Exclude apps by default
        "EXCLUDED_APPS": ["django_celery_beat", "oauth2_provider"],

        # Fail on warning in addition to errors
        "FAIL_ON_WARNING": False,
    }
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from django_safe_migrations.rules.base import Severity

# Default configuration values
DEFAULTS: dict[str, Any] = {
    "DISABLED_RULES": [],
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
