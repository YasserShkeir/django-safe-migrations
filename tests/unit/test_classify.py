"""Tests for deployment-phase classification (django_safe_migrations.classify)."""

from __future__ import annotations

import json
from io import StringIO

from django.db import migrations, models

from django_safe_migrations.classify import (
    Phase,
    classify_all,
    classify_migration,
    classify_operation,
    render_report,
)


class _FakeMigration:
    def __init__(self, operations):
        self.operations = operations


class TestClassifyOperation:
    """Per-operation category classification."""

    def test_add_field_is_expand(self):
        """An AddField is an additive (expand) operation."""
        op = migrations.AddField("Order", "total", models.IntegerField(default=0))
        assert classify_operation(op) == "expand"

    def test_create_model_is_expand(self):
        """A CreateModel is additive."""
        op = migrations.CreateModel(
            "Invoice", fields=[("id", models.AutoField(primary_key=True))]
        )
        assert classify_operation(op) == "expand"

    def test_remove_field_is_contract(self):
        """A RemoveField requires the old code to be gone first (contract)."""
        assert (
            classify_operation(migrations.RemoveField("Order", "total")) == "contract"
        )

    def test_rename_field_is_contract(self):
        """A RenameField is an in-place change needing coordination."""
        op = migrations.RenameField("Order", "total", "grand_total")
        assert classify_operation(op) == "contract"

    def test_alter_field_is_contract(self):
        """An AlterField is treated conservatively as contract."""
        op = migrations.AlterField("Order", "total", models.BigIntegerField())
        assert classify_operation(op) == "contract"

    def test_run_python_is_data(self):
        """A RunPython operation is a data operation."""
        assert classify_operation(migrations.RunPython(migrations.RunPython.noop)) == (
            "data"
        )

    def test_alter_model_options_is_neutral(self):
        """Python-only model option changes do not affect the phase."""
        op = migrations.AlterModelOptions("Order", options={"ordering": ["id"]})
        assert classify_operation(op) is None


class TestClassifyMigration:
    """Whole-migration aggregation."""

    def test_only_expand(self):
        """A migration with only additive ops is EXPAND."""
        mig = _FakeMigration(
            [
                migrations.AddField("Order", "a", models.IntegerField(default=0)),
                migrations.AddIndex(
                    "Order", models.Index(fields=["a"], name="order_a_idx")
                ),
            ]
        )
        phase, counts = classify_migration(mig)
        assert phase is Phase.EXPAND
        assert counts["expand"] == 2

    def test_only_contract(self):
        """A migration with only removals is CONTRACT."""
        mig = _FakeMigration([migrations.RemoveField("Order", "a")])
        assert classify_migration(mig)[0] is Phase.CONTRACT

    def test_only_data(self):
        """A data-only migration is DATA."""
        mig = _FakeMigration([migrations.RunPython(migrations.RunPython.noop)])
        assert classify_migration(mig)[0] is Phase.DATA

    def test_mixed(self):
        """Combining expand and contract yields MIXED."""
        mig = _FakeMigration(
            [
                migrations.AddField("Order", "a", models.IntegerField(default=0)),
                migrations.RemoveField("Order", "b"),
            ]
        )
        assert classify_migration(mig)[0] is Phase.MIXED

    def test_empty(self):
        """A migration with only neutral ops is EMPTY."""
        mig = _FakeMigration(
            [migrations.AlterModelOptions("Order", options={"ordering": ["id"]})]
        )
        assert classify_migration(mig)[0] is Phase.EMPTY

    def test_recurses_into_separate_database_and_state(self):
        """database_operations inside SeparateDatabaseAndState are counted."""
        mig = _FakeMigration(
            [
                migrations.SeparateDatabaseAndState(
                    database_operations=[migrations.RemoveField("Order", "a")]
                )
            ]
        )
        assert classify_migration(mig)[0] is Phase.CONTRACT


class TestClassifyAll:
    """Loader-based classification of the test project."""

    def test_classifies_testapp(self):
        """The testapp migrations are classified with valid phase labels."""
        results = classify_all(app_labels=["testapp"])
        assert results
        valid = {p.value for p in Phase}
        for r in results:
            assert r["app_label"] == "testapp"
            assert r["phase"] in valid

    def test_exclude_apps(self):
        """Excluded apps are omitted from the results."""
        results = classify_all(exclude_apps=["testapp"])
        assert all(r["app_label"] != "testapp" for r in results)


class TestRenderReport:
    """Report rendering."""

    def test_json_output(self):
        """JSON output is parseable and wraps a migrations list."""
        results = [
            {
                "app_label": "shop",
                "migration_name": "0001_initial",
                "phase": "expand",
                "counts": {"expand": 1, "contract": 0, "data": 0},
            }
        ]
        out = StringIO()
        render_report(results, "json", out)
        data = json.loads(out.getvalue())
        assert data["migrations"][0]["phase"] == "expand"

    def test_console_output(self):
        """Console output includes the phase and a summary line."""
        results = [
            {
                "app_label": "shop",
                "migration_name": "0001_initial",
                "phase": "expand",
                "counts": {"expand": 1, "contract": 0, "data": 0},
            }
        ]
        out = StringIO()
        render_report(results, "console", out)
        text = out.getvalue()
        assert "expand" in text
        assert "Summary" in text

    def test_console_empty(self):
        """An empty result set renders a friendly message."""
        out = StringIO()
        render_report([], "console", out)
        assert "No migrations" in out.getvalue()
