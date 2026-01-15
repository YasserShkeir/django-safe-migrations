"""Tests for configuration module."""

from __future__ import annotations

from unittest.mock import patch

from django_safe_migrations.conf import (
    get_config,
    get_disabled_rules,
    get_excluded_apps,
    get_fail_on_warning,
    get_rule_severity,
    get_severity_overrides,
    is_rule_disabled,
)
from django_safe_migrations.rules.base import Severity


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_defaults_when_no_settings(self):
        """Test returns default values when SAFE_MIGRATIONS is not set."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = None
            delattr(mock_settings, "SAFE_MIGRATIONS")

            config = get_config()

            assert config["DISABLED_RULES"] == []
            assert config["RULE_SEVERITY"] == {}
            assert "admin" in config["EXCLUDED_APPS"]
            assert config["FAIL_ON_WARNING"] is False

    def test_merges_user_settings_with_defaults(self):
        """Test merges user settings with defaults."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM006"],
                "FAIL_ON_WARNING": True,
            }

            config = get_config()

            assert config["DISABLED_RULES"] == ["SM006"]
            assert config["FAIL_ON_WARNING"] is True
            # Default values still present
            assert config["RULE_SEVERITY"] == {}


class TestGetDisabledRules:
    """Tests for get_disabled_rules function."""

    def test_returns_empty_list_by_default(self):
        """Test returns empty list when no rules disabled."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_disabled_rules()

            assert result == []

    def test_returns_disabled_rules_from_settings(self):
        """Test returns disabled rules from settings."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM006", "SM008"],
            }

            result = get_disabled_rules()

            assert result == ["SM006", "SM008"]


class TestIsRuleDisabled:
    """Tests for is_rule_disabled function."""

    def test_returns_false_for_enabled_rule(self):
        """Test returns False for rule not in disabled list."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM006"],
            }

            assert is_rule_disabled("SM001") is False

    def test_returns_true_for_disabled_rule(self):
        """Test returns True for rule in disabled list."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM006", "SM008"],
            }

            assert is_rule_disabled("SM006") is True
            assert is_rule_disabled("SM008") is True


class TestGetSeverityOverrides:
    """Tests for get_severity_overrides function."""

    def test_returns_empty_dict_by_default(self):
        """Test returns empty dict when no overrides set."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_severity_overrides()

            assert result == {}

    def test_converts_string_severity_to_enum(self):
        """Test converts string severity names to Severity enum."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {
                    "SM002": "info",
                    "SM006": "WARNING",
                },
            }

            result = get_severity_overrides()

            assert result["SM002"] == Severity.INFO
            assert result["SM006"] == Severity.WARNING

    def test_handles_uppercase_severity_names(self):
        """Test handles uppercase severity names."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {
                    "SM001": "ERROR",
                },
            }

            result = get_severity_overrides()

            assert result["SM001"] == Severity.ERROR

    def test_preserves_severity_enum_values(self):
        """Test preserves Severity enum values passed directly."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {
                    "SM001": Severity.INFO,
                },
            }

            result = get_severity_overrides()

            assert result["SM001"] == Severity.INFO


class TestGetRuleSeverity:
    """Tests for get_rule_severity function."""

    def test_returns_default_when_no_override(self):
        """Test returns default severity when no override set."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_rule_severity("SM001", Severity.ERROR)

            assert result == Severity.ERROR

    def test_returns_override_when_set(self):
        """Test returns override severity when set."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {
                    "SM002": "info",
                },
            }

            result = get_rule_severity("SM002", Severity.WARNING)

            assert result == Severity.INFO


class TestGetExcludedApps:
    """Tests for get_excluded_apps function."""

    def test_returns_defaults_when_not_set(self):
        """Test returns default excluded apps."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_excluded_apps()

            assert "admin" in result
            assert "auth" in result
            assert "contenttypes" in result

    def test_returns_custom_excluded_apps(self):
        """Test returns custom excluded apps from settings."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "EXCLUDED_APPS": ["myapp", "otherapp"],
            }

            result = get_excluded_apps()

            assert result == ["myapp", "otherapp"]


class TestGetFailOnWarning:
    """Tests for get_fail_on_warning function."""

    def test_returns_false_by_default(self):
        """Test returns False by default."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_fail_on_warning()

            assert result is False

    def test_returns_true_when_set(self):
        """Test returns True when configured."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "FAIL_ON_WARNING": True,
            }

            result = get_fail_on_warning()

            assert result is True
