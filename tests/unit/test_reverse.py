"""Tests for reverse-migration safety checks (django_safe_migrations.reverse)."""

from __future__ import annotations

from django.db import migrations, models

from django_safe_migrations.reverse import (
    _check_operation_reverse,
    analyze_reverse_safety,
)
from django_safe_migrations.rules.base import Severity


class _FakeMigration:
    """Minimal stand-in exposing only ``operations``."""

    def __init__(self, operations):
        self.operations = operations


class TestCheckOperationReverse:
    """Per-operation reverse classification."""

    def test_add_field_is_rv001(self):
        """A forward AddField reverses to a destructive DROP COLUMN."""
        op = migrations.AddField("Order", "total", models.IntegerField(default=0))
        issue = _check_operation_reverse(op)
        assert issue is not None
        assert issue.rule_id == "RV001"
        assert issue.severity is Severity.WARNING
        assert "Order" in issue.message and "total" in issue.message

    def test_create_model_is_rv002(self):
        """A forward CreateModel reverses to DROP TABLE."""
        op = migrations.CreateModel(
            "Invoice", fields=[("id", models.AutoField(primary_key=True))]
        )
        issue = _check_operation_reverse(op)
        assert issue is not None
        assert issue.rule_id == "RV002"
        assert issue.severity is Severity.WARNING
        assert "Invoice" in issue.message

    def test_add_index_is_rv003(self):
        """A forward AddIndex reverses to DROP INDEX (a brief lock)."""
        op = migrations.AddIndex(
            "Order", models.Index(fields=["total"], name="order_total_idx")
        )
        issue = _check_operation_reverse(op)
        assert issue is not None
        assert issue.rule_id == "RV003"
        assert issue.severity is Severity.INFO
        assert "order_total_idx" in issue.message

    def test_add_constraint_is_rv004(self):
        """A forward AddConstraint reverses to DROP CONSTRAINT."""
        op = migrations.AddConstraint(
            "Order",
            models.UniqueConstraint(fields=["total"], name="order_total_uniq"),
        )
        issue = _check_operation_reverse(op)
        assert issue is not None
        assert issue.rule_id == "RV004"
        assert issue.severity is Severity.INFO
        assert "order_total_uniq" in issue.message

    def test_remove_field_is_out_of_scope(self):
        """The RemoveField reverse needs lost state and is intentionally skipped."""
        op = migrations.RemoveField("Order", "total")
        assert _check_operation_reverse(op) is None

    def test_alter_field_is_out_of_scope(self):
        """The AlterField reverse needs the old field and is skipped."""
        op = migrations.AlterField("Order", "total", models.BigIntegerField())
        assert _check_operation_reverse(op) is None


class TestAnalyzeReverseSafety:
    """The migration-level reverse pass."""

    def test_collects_and_enriches(self):
        """Issues are collected and enriched with location metadata."""
        mig = _FakeMigration(
            [
                migrations.AddField("Order", "total", models.IntegerField(default=0)),
                migrations.RemoveField("Order", "old"),  # skipped
                migrations.CreateModel(
                    "Invoice", fields=[("id", models.AutoField(primary_key=True))]
                ),
            ]
        )
        issues = analyze_reverse_safety(
            mig,
            app_label="shop",
            migration_name="0005_things",
            file_path="/x/0005_things.py",
        )

        assert [i.rule_id for i in issues] == ["RV001", "RV002"]
        for issue in issues:
            assert issue.app_label == "shop"
            assert issue.migration_name == "0005_things"
            assert issue.file_path == "/x/0005_things.py"
        # operation_index points at the forward op (CreateModel is index 2).
        assert issues[1].operation_index == 2

    def test_no_operations_no_issues(self):
        """A migration with no reversible-danger ops yields nothing."""
        mig = _FakeMigration([migrations.RemoveField("Order", "total")])
        assert analyze_reverse_safety(mig) == []


class TestAnalyzerIntegration:
    """The analyzer only emits RV issues when check_reverse is enabled."""

    def test_check_reverse_off_by_default(self):
        """Without the flag, no RV issues are produced for testapp."""
        from django_safe_migrations.analyzer import MigrationAnalyzer

        issues = MigrationAnalyzer().analyze_app("testapp")
        assert not any(i.rule_id.startswith("RV") for i in issues)

    def test_check_reverse_emits_rv_issues(self):
        """With the flag, testapp's additive migrations surface RV issues."""
        from django_safe_migrations.analyzer import MigrationAnalyzer

        issues = MigrationAnalyzer(check_reverse=True).analyze_app("testapp")
        assert any(i.rule_id.startswith("RV") for i in issues)
