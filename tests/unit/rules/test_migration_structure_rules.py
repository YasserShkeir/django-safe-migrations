"""Tests for migration-structure rules (SM038, SM054)."""

from __future__ import annotations

from django.db import migrations, models

from django_safe_migrations.rules.migration_structure import (
    MixedSchemaAndDataRule,
    MultipleHeavyOpsSameTableRule,
)


def _noop(apps, schema_editor):
    pass


class TestMixedSchemaAndDataRule:
    """Tests for MixedSchemaAndDataRule (SM038)."""

    def test_flags_schema_plus_runpython(self, mock_migration_factory):
        """A migration with a schema op and a RunPython is flagged."""
        mig = mock_migration_factory(
            [
                migrations.AddField(
                    "user", "email", models.CharField(max_length=50, null=True)
                ),
                migrations.RunPython(_noop, migrations.RunPython.noop),
            ]
        )
        issues = MixedSchemaAndDataRule().check_migration(mig)
        assert len(issues) == 1
        assert issues[0].rule_id == "SM038"

    def test_flags_schema_plus_runsql_dml(self, mock_migration_factory):
        """A migration with a schema op and a RunSQL DML is flagged."""
        mig = mock_migration_factory(
            [
                migrations.AddField(
                    "user", "email", models.CharField(max_length=50, null=True)
                ),
                migrations.RunSQL("UPDATE app_user SET email = ''"),
            ]
        )
        assert MixedSchemaAndDataRule().check_migration(mig)

    def test_allows_schema_only(self, mock_migration_factory):
        """A schema-only migration is not flagged."""
        mig = mock_migration_factory(
            [
                migrations.AddField(
                    "user", "email", models.CharField(max_length=50, null=True)
                ),
                migrations.AddField(
                    "user", "phone", models.CharField(max_length=20, null=True)
                ),
            ]
        )
        assert MixedSchemaAndDataRule().check_migration(mig) == []

    def test_allows_runsql_ddl_with_schema(self, mock_migration_factory):
        """Pure-DDL RunSQL alongside schema ops is not 'data' (no flag)."""
        mig = mock_migration_factory(
            [
                migrations.AddField(
                    "user", "email", models.CharField(max_length=50, null=True)
                ),
                migrations.RunSQL("CREATE INDEX ix ON app_user (email)"),
            ]
        )
        assert MixedSchemaAndDataRule().check_migration(mig) == []


class TestMultipleHeavyOpsSameTableRule:
    """Tests for MultipleHeavyOpsSameTableRule (SM054)."""

    def test_flags_three_heavy_ops_same_table(self, mock_migration_factory):
        """Three heavy ops on one table are flagged."""
        mig = mock_migration_factory(
            [
                migrations.AddField("user", "a", models.IntegerField(null=True)),
                migrations.AlterField("user", "b", models.IntegerField()),
                migrations.AddIndex("user", models.Index(fields=["a"], name="ix_a")),
            ]
        )
        issues = MultipleHeavyOpsSameTableRule().check_migration(mig)
        assert len(issues) == 1
        assert issues[0].rule_id == "SM054"

    def test_allows_ops_on_different_tables(self, mock_migration_factory):
        """Heavy ops spread across tables are not flagged."""
        mig = mock_migration_factory(
            [
                migrations.AddField("user", "a", models.IntegerField(null=True)),
                migrations.AddField("order", "b", models.IntegerField(null=True)),
                migrations.AddField("item", "c", models.IntegerField(null=True)),
            ]
        )
        assert MultipleHeavyOpsSameTableRule().check_migration(mig) == []

    def test_allows_two_heavy_ops(self, mock_migration_factory):
        """Two heavy ops on one table is below the threshold."""
        mig = mock_migration_factory(
            [
                migrations.AddField("user", "a", models.IntegerField(null=True)),
                migrations.AlterField("user", "b", models.IntegerField()),
            ]
        )
        assert MultipleHeavyOpsSameTableRule().check_migration(mig) == []
