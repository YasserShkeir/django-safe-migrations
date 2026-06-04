"""Tests for BaseRule shared behavior (db + Django version gating)."""

from __future__ import annotations

from typing import Optional

from django_safe_migrations.rules.base import BaseRule, Issue, Severity


class _NoopRule(BaseRule):
    """Minimal concrete rule for exercising the gating helpers."""

    rule_id = "SMTEST"
    severity = Severity.INFO
    description = "test"

    def check(self, operation, migration, **kwargs) -> Optional[Issue]:
        return None


class TestAppliesToDjango:
    """Tests for the django_min_version gate."""

    def test_default_applies_to_all_versions(self):
        """A rule with no django_min_version applies everywhere."""
        rule = _NoopRule()
        assert rule.django_min_version is None
        assert rule.applies_to_django() is True

    def test_future_version_does_not_apply(self):
        """A rule requiring a newer Django than installed is skipped."""

        class FutureRule(_NoopRule):
            django_min_version = (99, 0)

        assert FutureRule().applies_to_django() is False

    def test_past_version_applies(self):
        """A rule requiring an old Django applies on any supported version."""

        class OldRule(_NoopRule):
            django_min_version = (3, 2)

        assert OldRule().applies_to_django() is True
