"""Tests for EXTRA_RULES plugin system."""

from __future__ import annotations

from unittest.mock import patch

from django_safe_migrations.rules import (
    ALL_RULES,
    _load_extra_rules,
    clear_extra_rules_cache,
    get_all_rule_ids,
    get_all_rules,
    get_rule_by_id,
)
from django_safe_migrations.rules.base import BaseRule, Severity


class MockCustomRule(BaseRule):
    """A mock custom rule for testing."""

    rule_id = "CUSTOM001"
    severity = Severity.WARNING
    description = "A custom test rule"

    def check(self, operation, migration, **kwargs):
        """Return None to indicate no issue found."""
        return None


class TestLoadExtraRules:
    """Tests for _load_extra_rules function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_extra_rules_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_extra_rules_cache()

    def test_returns_empty_when_no_extra_rules(self):
        """Test returns empty list when no EXTRA_RULES configured."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            result = _load_extra_rules()

            assert result == []

    def test_loads_valid_rule_class(self):
        """Test loads valid rule class from path."""
        # Use the mock rule we defined in this file
        rule_path = "tests.unit.rules.test_extra_rules.MockCustomRule"

        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = [rule_path]

            result = _load_extra_rules()

            assert len(result) == 1
            assert result[0] == MockCustomRule

    def test_skips_invalid_import(self):
        """Test skips rules that fail to import."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = ["nonexistent.module.Rule"]

            result = _load_extra_rules()

            # Should return empty list, not raise exception
            assert result == []

    def test_skips_non_baserule_class(self):
        """Test skips classes that don't inherit from BaseRule."""
        # str is not a BaseRule subclass
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = ["builtins.str"]

            result = _load_extra_rules()

            # Should skip str since it's not a BaseRule
            assert result == []

    def test_caches_results(self):
        """Test that results are cached."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            # First call
            _load_extra_rules()
            # Second call
            _load_extra_rules()

            # Should only call get_extra_rules once due to caching
            assert mock_get.call_count == 1


class TestClearExtraRulesCache:
    """Tests for clear_extra_rules_cache function."""

    def test_clears_cache(self):
        """Test that cache is cleared."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            # First call - populates cache
            _load_extra_rules()

            # Clear cache
            clear_extra_rules_cache()

            # Second call - should call get_extra_rules again
            _load_extra_rules()

            # Should have called twice now
            assert mock_get.call_count == 2


class TestGetAllRulesWithExtras:
    """Tests for get_all_rules with EXTRA_RULES."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_extra_rules_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_extra_rules_cache()

    def test_includes_builtin_rules(self):
        """Test that builtin rules are included."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            rules = get_all_rules("postgresql")

            # Should have all builtin rules
            rule_ids = {r.rule_id for r in rules}
            assert "SM001" in rule_ids  # NotNullWithoutDefaultRule
            assert "SM010" in rule_ids  # UnsafeIndexCreationRule

    def test_includes_custom_rules(self):
        """Test that custom rules are included."""
        rule_path = "tests.unit.rules.test_extra_rules.MockCustomRule"

        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = [rule_path]

            rules = get_all_rules("postgresql")

            rule_ids = {r.rule_id for r in rules}
            assert "CUSTOM001" in rule_ids


class TestGetAllRuleIdsWithExtras:
    """Tests for get_all_rule_ids with EXTRA_RULES."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_extra_rules_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_extra_rules_cache()

    def test_includes_custom_rule_ids(self):
        """Test that custom rule IDs are included."""
        rule_path = "tests.unit.rules.test_extra_rules.MockCustomRule"

        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = [rule_path]

            rule_ids = get_all_rule_ids()

            assert "CUSTOM001" in rule_ids
            assert "SM001" in rule_ids  # Builtin still there


class TestGetRuleByIdWithExtras:
    """Tests for get_rule_by_id with EXTRA_RULES."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_extra_rules_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_extra_rules_cache()

    def test_finds_builtin_rule(self):
        """Test finding builtin rule by ID."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            rule_cls = get_rule_by_id("SM001")

            assert rule_cls is not None
            assert rule_cls().rule_id == "SM001"

    def test_finds_custom_rule(self):
        """Test finding custom rule by ID."""
        rule_path = "tests.unit.rules.test_extra_rules.MockCustomRule"

        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = [rule_path]

            rule_cls = get_rule_by_id("CUSTOM001")

            assert rule_cls is not None
            assert rule_cls == MockCustomRule

    def test_returns_none_for_unknown_id(self):
        """Test returns None for unknown rule ID."""
        with patch("django_safe_migrations.conf.get_extra_rules") as mock_get:
            mock_get.return_value = []

            rule_cls = get_rule_by_id("NONEXISTENT")

            assert rule_cls is None


class TestAllRulesRegistry:
    """Tests for ALL_RULES registry."""

    def test_all_rules_contains_expected_count(self):
        """Test ALL_RULES contains expected number of rules."""
        # v0.5.0 has 36 built-in rules (SM001-SM036)
        assert len(ALL_RULES) == 36

    def test_all_rules_have_unique_ids(self):
        """Test all rules have unique IDs."""
        rule_ids = [r().rule_id for r in ALL_RULES]
        assert len(rule_ids) == len(set(rule_ids))

    def test_all_rules_are_baserule_subclasses(self):
        """Test all rules inherit from BaseRule."""
        for rule_cls in ALL_RULES:
            assert issubclass(rule_cls, BaseRule)

    def test_new_v040_rules_present(self):
        """Test v0.4.0 new rules are registered."""
        rule_ids = {r().rule_id for r in ALL_RULES}

        # New rules in v0.4.0
        assert "SM020" in rule_ids  # AlterFieldNullFalseRule
        assert "SM021" in rule_ids  # AlterFieldUniqueRule
        assert "SM022" in rule_ids  # ExpensiveDefaultCallableRule
        assert "SM023" in rule_ids  # AddManyToManyRule
        assert "SM024" in rule_ids  # SQLInjectionPatternRule
        assert "SM025" in rule_ids  # ForeignKeyWithoutIndexRule
        assert "SM026" in rule_ids  # RunPythonNoBatchingRule

    def test_new_v050_rules_present(self):
        """Test v0.5.0 new rules are registered."""
        rule_ids = {r().rule_id for r in ALL_RULES}

        assert "SM027" in rule_ids  # MissingMergeMigrationRule
        assert "SM028" in rule_ids  # PreferBigIntRule
        assert "SM029" in rule_ids  # DropNotNullRule
        assert "SM030" in rule_ids  # UnsafeIndexDeletionRule
        assert "SM031" in rule_ids  # PreferTextOverVarcharRule
        assert "SM032" in rule_ids  # PreferTimestampTZRule
        assert "SM033" in rule_ids  # AddFieldWithDefaultRule
        assert "SM034" in rule_ids  # PreferIdentityRule
        assert "SM035" in rule_ids  # RequireLockTimeoutRule
        assert "SM036" in rule_ids  # PreferIfExistsRule
