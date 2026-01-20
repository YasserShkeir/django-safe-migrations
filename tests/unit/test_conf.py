"""Tests for configuration module."""

from __future__ import annotations

from unittest.mock import patch

from django_safe_migrations.conf import (
    RULE_CATEGORIES,
    get_all_categories,
    get_app_config,
    get_app_rules_config,
    get_category_for_rule,
    get_config,
    get_disabled_categories,
    get_disabled_rules,
    get_enabled_categories,
    get_excluded_apps,
    get_fail_on_warning,
    get_rule_severity,
    get_rule_severity_for_app,
    get_rules_from_categories,
    get_rules_in_category,
    get_severity_overrides,
    is_rule_disabled,
    is_rule_disabled_by_category,
    is_rule_enabled,
    is_rule_enabled_for_app,
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


class TestRuleCategories:
    """Tests for rule category constants."""

    def test_rule_categories_is_dict(self):
        """Test RULE_CATEGORIES is a dictionary."""
        assert isinstance(RULE_CATEGORIES, dict)

    def test_all_categories_have_list_values(self):
        """Test all category values are lists."""
        for category, rules in RULE_CATEGORIES.items():
            assert isinstance(rules, list), f"Category {category} value should be list"

    def test_postgresql_category_contains_expected_rules(self):
        """Test PostgreSQL category contains expected rules."""
        pg_rules = RULE_CATEGORIES.get("postgresql", [])
        # SM010 and SM011 are index-related PostgreSQL rules
        assert "SM010" in pg_rules
        assert "SM011" in pg_rules
        assert "SM018" in pg_rules  # Concurrent operations

    def test_destructive_category_exists(self):
        """Test destructive category exists with expected rules."""
        assert "destructive" in RULE_CATEGORIES
        destructive_rules = RULE_CATEGORIES["destructive"]
        assert "SM002" in destructive_rules  # RemoveField
        assert "SM003" in destructive_rules  # DeleteModel


class TestGetDisabledCategories:
    """Tests for get_disabled_categories function."""

    def test_returns_empty_list_by_default(self):
        """Test returns empty list when no categories disabled."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_disabled_categories()

            assert result == []

    def test_returns_disabled_categories_from_settings(self):
        """Test returns disabled categories from settings."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_CATEGORIES": ["reversibility", "informational"],
            }

            result = get_disabled_categories()

            assert result == ["reversibility", "informational"]


class TestGetEnabledCategories:
    """Tests for get_enabled_categories function."""

    def test_returns_empty_list_by_default(self):
        """Test returns empty list (all enabled) by default."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_enabled_categories()

            assert result == []

    def test_returns_enabled_categories_from_settings(self):
        """Test returns enabled categories from settings."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "ENABLED_CATEGORIES": ["high-risk", "destructive"],
            }

            result = get_enabled_categories()

            assert result == ["high-risk", "destructive"]


class TestGetRulesInCategory:
    """Tests for get_rules_in_category function."""

    def test_returns_rules_for_valid_category(self):
        """Test returns rules for existing category."""
        result = get_rules_in_category("postgresql")

        assert isinstance(result, list)
        assert len(result) > 0
        assert "SM010" in result

    def test_returns_empty_list_for_unknown_category(self):
        """Test returns empty list for unknown category."""
        result = get_rules_in_category("nonexistent_category")

        assert result == []

    def test_returns_expected_rules_for_indexes(self):
        """Test indexes category contains expected rules."""
        result = get_rules_in_category("indexes")

        assert "SM010" in result  # UnsafeIndexCreation
        assert "SM011" in result  # UnsafeUniqueConstraint
        assert "SM018" in result  # ConcurrentInAtomic


class TestGetAllCategories:
    """Tests for get_all_categories function."""

    def test_returns_all_category_names(self):
        """Test returns all category names as list."""
        result = get_all_categories()

        assert isinstance(result, list)
        assert "postgresql" in result
        assert "indexes" in result
        assert "destructive" in result
        assert "high-risk" in result

    def test_matches_rule_categories_keys(self):
        """Test result matches RULE_CATEGORIES keys."""
        result = get_all_categories()

        assert set(result) == set(RULE_CATEGORIES.keys())


class TestGetRulesFromCategories:
    """Tests for get_rules_from_categories function."""

    def test_returns_empty_set_for_empty_list(self):
        """Test returns empty set for empty categories list."""
        result = get_rules_from_categories([])

        assert result == set()

    def test_returns_rules_from_single_category(self):
        """Test returns rules from single category."""
        result = get_rules_from_categories(["indexes"])

        assert isinstance(result, set)
        assert "SM010" in result
        assert "SM011" in result

    def test_returns_union_of_multiple_categories(self):
        """Test returns union of rules from multiple categories."""
        result = get_rules_from_categories(["indexes", "destructive"])

        # Should contain index rules
        assert "SM010" in result
        assert "SM011" in result
        # Should also contain destructive rules
        assert "SM002" in result
        assert "SM003" in result

    def test_deduplicates_rules(self):
        """Test that rules appearing in multiple categories are deduplicated."""
        # Get rules from overlapping categories
        result = get_rules_from_categories(["postgresql", "indexes"])

        # SM010 appears in both - should only appear once
        rule_list = list(result)
        assert rule_list.count("SM010") == 1


class TestIsRuleDisabledByCategory:
    """Tests for is_rule_disabled_by_category function."""

    def test_returns_false_when_no_category_config(self):
        """Test returns False when no category configuration."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = is_rule_disabled_by_category("SM001")

            assert result is False

    def test_returns_true_for_rule_in_disabled_category(self):
        """Test returns True for rule in disabled category."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_CATEGORIES": ["indexes"],
            }

            # SM010 is in indexes category
            result = is_rule_disabled_by_category("SM010")

            assert result is True

    def test_returns_false_for_rule_not_in_disabled_category(self):
        """Test returns False for rule not in disabled category."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_CATEGORIES": ["indexes"],
            }

            # SM001 is not in indexes category
            result = is_rule_disabled_by_category("SM001")

            assert result is False

    def test_whitelist_mode_disables_rules_not_in_enabled_categories(self):
        """Test whitelist mode disables rules not in enabled categories."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "ENABLED_CATEGORIES": ["indexes"],
            }

            # SM001 is not in indexes category
            result = is_rule_disabled_by_category("SM001")

            assert result is True

    def test_whitelist_mode_enables_rules_in_enabled_categories(self):
        """Test whitelist mode enables rules in enabled categories."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "ENABLED_CATEGORIES": ["indexes"],
            }

            # SM010 is in indexes category
            result = is_rule_disabled_by_category("SM010")

            assert result is False


class TestIsRuleEnabled:
    """Tests for is_rule_enabled function."""

    def test_returns_true_for_enabled_rule(self):
        """Test returns True for rule that is enabled."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = is_rule_enabled("SM001")

            assert result is True

    def test_returns_false_for_individually_disabled_rule(self):
        """Test returns False for rule in DISABLED_RULES."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM001"],
            }

            result = is_rule_enabled("SM001")

            assert result is False

    def test_returns_false_for_rule_disabled_by_category(self):
        """Test returns False for rule disabled by category."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_CATEGORIES": ["indexes"],
            }

            # SM010 is in indexes category
            result = is_rule_enabled("SM010")

            assert result is False

    def test_individual_disable_takes_precedence(self):
        """Test individual disable overrides category enable."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM010"],
                "ENABLED_CATEGORIES": ["indexes"],  # SM010 is in this
            }

            # Even though indexes is enabled, SM010 is individually disabled
            result = is_rule_enabled("SM010")

            assert result is False


class TestGetCategoryForRule:
    """Tests for get_category_for_rule function."""

    def test_returns_categories_for_rule(self):
        """Test returns all categories containing rule."""
        result = get_category_for_rule("SM010")

        assert isinstance(result, list)
        assert "postgresql" in result
        assert "indexes" in result

    def test_returns_empty_list_for_unknown_rule(self):
        """Test returns empty list for rule not in any category."""
        result = get_category_for_rule("SM999")

        assert result == []

    def test_returns_multiple_categories_for_rule(self):
        """Test returns multiple categories when rule belongs to many."""
        result = get_category_for_rule("SM002")

        # SM002 (RemoveField) should be in destructive and data-loss
        assert "destructive" in result
        assert "data-loss" in result


# -----------------------------------------------------------------------------
# Per-App Configuration Tests
# -----------------------------------------------------------------------------


class TestGetAppRulesConfig:
    """Tests for get_app_rules_config function."""

    def test_returns_empty_dict_by_default(self):
        """Test returns empty dict when no APP_RULES configured."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_app_rules_config()

            assert result == {}

    def test_returns_app_rules_from_settings(self):
        """Test returns APP_RULES from settings."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "myapp": {"DISABLED_RULES": ["SM001"]},
                    "otherapp": {"ENABLED_CATEGORIES": ["indexes"]},
                }
            }

            result = get_app_rules_config()

            assert "myapp" in result
            assert "otherapp" in result
            assert result["myapp"]["DISABLED_RULES"] == ["SM001"]


class TestGetAppConfig:
    """Tests for get_app_config function."""

    def test_returns_empty_dict_for_unconfigured_app(self):
        """Test returns empty dict for app not in APP_RULES."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "myapp": {"DISABLED_RULES": ["SM001"]},
                }
            }

            result = get_app_config("unconfigured_app")

            assert result == {}

    def test_returns_config_for_configured_app(self):
        """Test returns config for app in APP_RULES."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "myapp": {
                        "DISABLED_RULES": ["SM001", "SM002"],
                        "RULE_SEVERITY": {"SM003": "INFO"},
                    },
                }
            }

            result = get_app_config("myapp")

            assert result["DISABLED_RULES"] == ["SM001", "SM002"]
            assert result["RULE_SEVERITY"] == {"SM003": "INFO"}


class TestIsRuleEnabledForApp:
    """Tests for is_rule_enabled_for_app function."""

    def test_returns_global_result_when_no_app(self):
        """Test falls back to global config when app_label is None."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM001"],
            }

            result = is_rule_enabled_for_app("SM001", None)

            assert result is False

    def test_returns_global_result_for_unconfigured_app(self):
        """Test falls back to global config for unconfigured app."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM001"],
                "APP_RULES": {},
            }

            result = is_rule_enabled_for_app("SM001", "unconfigured_app")

            assert result is False

    def test_app_disabled_rules_take_precedence(self):
        """Test app-specific DISABLED_RULES disables rule."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "legacy_app": {"DISABLED_RULES": ["SM001", "SM002"]},
                }
            }

            # SM001 disabled for legacy_app
            assert is_rule_enabled_for_app("SM001", "legacy_app") is False
            # SM003 not disabled for legacy_app
            assert is_rule_enabled_for_app("SM003", "legacy_app") is True

    def test_app_enabled_categories_whitelist(self):
        """Test app-specific ENABLED_CATEGORIES creates whitelist."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "strict_app": {"ENABLED_CATEGORIES": ["indexes"]},
                }
            }

            # SM010 is in indexes category - should be enabled
            assert is_rule_enabled_for_app("SM010", "strict_app") is True
            # SM001 is not in indexes category - should be disabled
            assert is_rule_enabled_for_app("SM001", "strict_app") is False

    def test_app_disabled_categories(self):
        """Test app-specific DISABLED_CATEGORIES disables rules."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "relaxed_app": {"DISABLED_CATEGORIES": ["indexes"]},
                }
            }

            # SM010 is in indexes category - should be disabled
            assert is_rule_enabled_for_app("SM010", "relaxed_app") is False
            # SM001 is not in indexes category - should be enabled
            assert is_rule_enabled_for_app("SM001", "relaxed_app") is True

    def test_global_disabled_still_applies(self):
        """Test global DISABLED_RULES still applies even with app config."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "DISABLED_RULES": ["SM005"],  # Globally disabled
                "APP_RULES": {
                    "myapp": {"DISABLED_RULES": ["SM001"]},  # App-specific disable
                },
            }

            # SM005 is globally disabled
            assert is_rule_enabled_for_app("SM005", "myapp") is False
            # SM001 is app-specifically disabled
            assert is_rule_enabled_for_app("SM001", "myapp") is False
            # SM002 is not disabled
            assert is_rule_enabled_for_app("SM002", "myapp") is True


class TestGetRuleSeverityForApp:
    """Tests for get_rule_severity_for_app function."""

    def test_returns_default_when_no_override(self):
        """Test returns default severity when no override."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {}

            result = get_rule_severity_for_app("SM001", Severity.ERROR, "myapp")

            assert result == Severity.ERROR

    def test_returns_global_override(self):
        """Test returns global severity override."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {"SM001": "INFO"},
            }

            result = get_rule_severity_for_app("SM001", Severity.ERROR, "myapp")

            assert result == Severity.INFO

    def test_app_override_takes_precedence(self):
        """Test app-specific severity takes precedence over global."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {"SM001": "WARNING"},  # Global override
                "APP_RULES": {
                    "legacy_app": {
                        "RULE_SEVERITY": {"SM001": "INFO"},  # App override
                    }
                },
            }

            # App override should take precedence
            result = get_rule_severity_for_app("SM001", Severity.ERROR, "legacy_app")
            assert result == Severity.INFO

            # Other apps use global
            result = get_rule_severity_for_app("SM001", Severity.ERROR, "other_app")
            assert result == Severity.WARNING

    def test_handles_uppercase_severity_in_app_config(self):
        """Test handles uppercase severity strings in app config."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "APP_RULES": {
                    "myapp": {"RULE_SEVERITY": {"SM001": "WARNING"}},
                }
            }

            result = get_rule_severity_for_app("SM001", Severity.ERROR, "myapp")

            assert result == Severity.WARNING

    def test_returns_global_when_no_app(self):
        """Test returns global severity when app_label is None."""
        with patch("django_safe_migrations.conf.settings") as mock_settings:
            mock_settings.SAFE_MIGRATIONS = {
                "RULE_SEVERITY": {"SM001": "INFO"},
            }

            result = get_rule_severity_for_app("SM001", Severity.ERROR, None)

            assert result == Severity.INFO
