"""Tests for the MigrationAnalyzer."""

from django.db import migrations, models
from django.test import override_settings

from django_safe_migrations.analyzer import MigrationAnalyzer


class TestMigrationAnalyzer:
    """Tests for MigrationAnalyzer."""

    def test_analyze_migration_finds_issues(self, mock_migration_factory):
        """Test that analyzer finds issues in a migration."""
        # Create migration with an unsafe operation
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),  # NOT NULL, no default
        )
        migration = mock_migration_factory([operation])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        assert len(issues) >= 1
        assert any(issue.rule_id == "SM001" for issue in issues)

    def test_analyze_migration_safe_operations(self, mock_migration_factory):
        """Test that analyzer doesn't flag safe operations."""
        # Create migration with safe operations
        operation = migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(max_length=100, null=True),
        )
        migration = mock_migration_factory([operation])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        # Should have no issues for nullable field
        sm001_issues = [i for i in issues if i.rule_id == "SM001"]
        assert len(sm001_issues) == 0

    def test_analyze_migration_multiple_operations(self, mock_migration_factory):
        """Test analyzer with multiple operations."""
        operations = [
            migrations.AddField(
                model_name="user",
                name="email",
                field=models.CharField(max_length=255),  # Unsafe
            ),
            migrations.AddField(
                model_name="user",
                name="nickname",
                field=models.CharField(max_length=100, null=True),  # Safe
            ),
            migrations.RemoveField(
                model_name="user",
                name="old_field",
            ),  # Warning
        ]
        migration = mock_migration_factory(operations)

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        # Should find SM001 (NOT NULL) and SM002 (RemoveField)
        rule_ids = {issue.rule_id for issue in issues}
        assert "SM001" in rule_ids
        assert "SM002" in rule_ids

    def test_db_vendor_filtering(self, mock_migration_factory):
        """Test that rules are filtered by database vendor."""
        # AddIndex is only flagged on PostgreSQL
        operation = migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="email_idx"),
        )
        migration = mock_migration_factory([operation])

        # PostgreSQL should flag this
        pg_analyzer = MigrationAnalyzer(db_vendor="postgresql")
        pg_issues = pg_analyzer.analyze_migration(migration)
        assert any(issue.rule_id == "SM010" for issue in pg_issues)

        # SQLite should not flag this
        sqlite_analyzer = MigrationAnalyzer(db_vendor="sqlite")
        sqlite_issues = sqlite_analyzer.analyze_migration(migration)
        assert not any(issue.rule_id == "SM010" for issue in sqlite_issues)

    def test_get_summary(self, mock_migration_factory):
        """Test summary generation."""
        operations = [
            migrations.AddField(
                model_name="user",
                name="email",
                field=models.CharField(max_length=255),  # Error
            ),
            migrations.RemoveField(
                model_name="user",
                name="old_field",
            ),  # Warning
        ]
        migration = mock_migration_factory([operations[0]])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)
        summary = analyzer.get_summary(issues)

        assert "total" in summary
        assert "by_severity" in summary
        assert "by_rule" in summary
        assert summary["total"] >= 1

    def test_custom_rules(self, mock_migration_factory):
        """Test analyzer with custom rule set."""
        from django_safe_migrations.rules.add_field import NotNullWithoutDefaultRule

        # Only use one specific rule
        analyzer = MigrationAnalyzer(
            rules=[NotNullWithoutDefaultRule()],
            db_vendor="postgresql",
        )

        operation = migrations.RemoveField(
            model_name="user",
            name="old_field",
        )
        migration = mock_migration_factory([operation])

        issues = analyzer.analyze_migration(migration)

        # Should not find SM002 because we only loaded SM001
        assert not any(issue.rule_id == "SM002" for issue in issues)

    def test_disabled_rules_via_constructor(self, mock_migration_factory):
        """Test that disabled_rules parameter skips specified rules."""
        operations = [
            migrations.AddField(
                model_name="user",
                name="email",
                field=models.CharField(max_length=255),  # Would trigger SM001
            ),
            migrations.RemoveField(
                model_name="user",
                name="old_field",
            ),  # Would trigger SM002
        ]
        migration = mock_migration_factory(operations)

        # Disable SM001
        analyzer = MigrationAnalyzer(
            db_vendor="postgresql",
            disabled_rules=["SM001"],
        )
        issues = analyzer.analyze_migration(migration)

        # SM001 should be skipped, SM002 should still be found
        assert not any(issue.rule_id == "SM001" for issue in issues)
        assert any(issue.rule_id == "SM002" for issue in issues)

    def test_is_rule_enabled_method(self, mock_migration_factory):
        """Test the _is_rule_enabled method."""
        analyzer_with_disabled = MigrationAnalyzer(
            db_vendor="postgresql",
            disabled_rules=["SM006", "SM008"],
        )

        # Disabled rules should return False for is_rule_enabled
        assert analyzer_with_disabled._is_rule_enabled("SM006") is False
        assert analyzer_with_disabled._is_rule_enabled("SM008") is False
        # Non-disabled rules should return True
        assert analyzer_with_disabled._is_rule_enabled("SM001") is True

        # Without explicit disabled_rules, it should check settings
        analyzer_default = MigrationAnalyzer(db_vendor="postgresql")
        # Will return True unless settings have DISABLED_RULES or DISABLED_CATEGORIES
        assert isinstance(analyzer_default._is_rule_enabled("SM001"), bool)


class TestErrorRecovery:
    """Tests for error recovery with malformed migrations."""

    def test_migration_without_operations(self, mock_migration_factory):
        """Test analyzer handles migration without operations list gracefully."""
        migration = mock_migration_factory([])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should not raise, returns empty list
        issues = analyzer.analyze_migration(migration)
        assert issues == []

    def test_migration_with_none_operation(self, mock_migration_factory):
        """Test analyzer handles None in operations list."""
        # Create a migration and manually set operations to include None
        migration = mock_migration_factory([])

        # Manually add None to operations
        migration.operations = [None]

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully, skipping None
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_operation_with_missing_attributes(self, mock_migration_factory):
        """Test analyzer handles operations with missing expected attributes."""

        class MalformedOperation:
            """An operation-like object missing expected attributes."""

            pass

        migration = mock_migration_factory([])
        migration.operations = [MalformedOperation()]

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_field_with_unusual_attributes(self):
        """Test analyzer handles fields with unusual attribute values."""

        class UnusualField:
            """A field with unexpected attribute types."""

            null = "not_a_bool"  # Should be bool
            default = object()  # Unusual default
            unique = 123  # Should be bool

        operation = migrations.AddField(
            model_name="user",
            name="test_field",
            field=UnusualField(),
        )

        from unittest.mock import Mock

        migration = Mock()
        migration.operations = [operation]
        migration.app_label = "testapp"
        migration.name = "0001_test"
        migration.__module__ = "testapp.migrations.0001_test"

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully without crashing
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_analyze_empty_app(self):
        """Test analyzer handles app with no migrations."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should return empty list for non-existent app
        issues = analyzer.analyze_app("nonexistent_app_12345")
        assert issues == []

    def test_runsql_with_none_sql(self, mock_migration_factory):
        """Test analyzer handles RunSQL with None sql."""
        operation = migrations.RunSQL(sql="", reverse_sql=None)

        migration = mock_migration_factory([operation])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_runpython_with_lambda(self, mock_migration_factory):
        """Test analyzer handles RunPython with lambda (no source available)."""
        operation = migrations.RunPython(
            code=lambda apps, schema_editor: None,
            reverse_code=None,
        )

        migration = mock_migration_factory([operation])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully (SM026 may skip due to no source)
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_unicode_in_field_names(self, mock_migration_factory):
        """Test analyzer handles unicode characters in field/model names."""
        operation = migrations.AddField(
            model_name="użytkownik",  # Polish for "user"
            name="imię",  # Polish for "name"
            field=models.CharField(max_length=100, null=True),
        )

        migration = mock_migration_factory([operation])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle unicode gracefully
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_very_long_field_names(self, mock_migration_factory):
        """Test analyzer handles very long field names."""
        long_name = "a" * 1000  # Very long field name

        operation = migrations.AddField(
            model_name="user",
            name=long_name,
            field=models.CharField(max_length=100, null=True),
        )

        migration = mock_migration_factory([operation])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)

    def test_migration_with_circular_reference(self):
        """Test analyzer handles migration with self-referential structures."""
        from unittest.mock import Mock

        migration = Mock()
        migration.operations = []
        migration.app_label = "testapp"
        migration.name = "0001_test"
        migration.__module__ = "testapp.migrations.0001_test"

        # Create circular reference
        migration.self_ref = migration

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully
        issues = analyzer.analyze_migration(migration)
        assert issues == []

    def test_operation_raising_exception_in_repr(self, mock_migration_factory):
        """Test analyzer handles operations that raise in __repr__."""

        class BadReprOperation:
            """An operation that raises in __repr__."""

            def __repr__(self):
                raise RuntimeError("Cannot repr this operation")

        migration = mock_migration_factory([])
        migration.operations = [BadReprOperation()]

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Should handle gracefully
        issues = analyzer.analyze_migration(migration)
        assert isinstance(issues, list)


class TestAnalyzeAll:
    """Tests for MigrationAnalyzer.analyze_all."""

    def test_analyze_all_excludes_apps(self):
        """Test that analyze_all respects exclude_apps parameter."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        # Exclude testapp — should get no testapp issues
        issues = analyzer.analyze_all(exclude_apps=["testapp"])
        testapp_issues = [i for i in issues if i.app_label == "testapp"]
        assert len(testapp_issues) == 0

    def test_analyze_all_includes_testapp(self):
        """Test that analyze_all finds issues in testapp when not excluded."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        # Exclude Django built-ins but include testapp
        issues = analyzer.analyze_all(
            exclude_apps=[
                "admin",
                "auth",
                "contenttypes",
                "sessions",
                "messages",
                "staticfiles",
            ]
        )
        testapp_issues = [i for i in issues if i.app_label == "testapp"]
        assert len(testapp_issues) > 0

    def test_analyze_all_exclude_multiple(self):
        """Test that multiple apps can be excluded."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_all(
            exclude_apps=["testapp", "admin", "auth", "contenttypes"]
        )
        for issue in issues:
            assert issue.app_label not in (
                "testapp",
                "admin",
                "auth",
                "contenttypes",
            )


class TestAnalyzeNewMigrations:
    """Tests for MigrationAnalyzer.analyze_new_migrations."""

    def _make_mock_loader(self, disk_migrations):
        """Create a mock MigrationLoader with given disk_migrations."""
        from unittest.mock import MagicMock

        loader = MagicMock()
        loader.disk_migrations = disk_migrations
        return loader

    def test_analyze_new_migrations_with_app_filter(self, mock_migration_factory):
        """Test analyze_new_migrations filters by app_label."""
        from unittest.mock import MagicMock, patch

        mig_testapp = mock_migration_factory(
            [migrations.RemoveField(model_name="user", name="old_field")],
            app_label="testapp",
            name="0001_initial",
        )
        mig_other = mock_migration_factory(
            [migrations.RemoveField(model_name="user", name="old_field")],
            app_label="otherapp",
            name="0001_initial",
        )

        disk = {
            ("testapp", "0001_initial"): mig_testapp,
            ("otherapp", "0001_initial"): mig_other,
        }
        mock_loader = self._make_mock_loader(disk)
        mock_loader.get_migration.side_effect = lambda app, name: disk[(app, name)]

        mock_recorder = MagicMock()
        mock_recorder.applied_migrations.return_value = set()

        with (
            patch(
                "django.db.migrations.loader.MigrationLoader",
                return_value=mock_loader,
            ),
            patch(
                "django.db.migrations.recorder.MigrationRecorder",
                return_value=mock_recorder,
            ),
        ):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
            issues = analyzer.analyze_new_migrations(app_label="testapp")
            for issue in issues:
                assert issue.app_label == "testapp"
            assert len(issues) > 0

    def test_analyze_new_migrations_nonexistent_app(self):
        """Test analyze_new_migrations with non-existent app returns empty."""
        from unittest.mock import MagicMock, patch

        mock_loader = self._make_mock_loader({("testapp", "0001_initial"): None})
        mock_recorder = MagicMock()
        mock_recorder.applied_migrations.return_value = set()

        with (
            patch(
                "django.db.migrations.loader.MigrationLoader",
                return_value=mock_loader,
            ),
            patch(
                "django.db.migrations.recorder.MigrationRecorder",
                return_value=mock_recorder,
            ),
        ):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
            issues = analyzer.analyze_new_migrations(app_label="nonexistent_app_xyz")
            assert issues == []

    def test_analyze_new_migrations_skips_applied(self, mock_migration_factory):
        """Test that already-applied migrations are skipped."""
        from unittest.mock import MagicMock, patch

        mig = mock_migration_factory(
            [migrations.RemoveField(model_name="user", name="old_field")],
            app_label="testapp",
            name="0001_initial",
        )
        disk = {("testapp", "0001_initial"): mig}
        mock_loader = self._make_mock_loader(disk)

        mock_recorder = MagicMock()
        # Mark the migration as already applied
        mock_recorder.applied_migrations.return_value = {("testapp", "0001_initial")}

        with (
            patch(
                "django.db.migrations.loader.MigrationLoader",
                return_value=mock_loader,
            ),
            patch(
                "django.db.migrations.recorder.MigrationRecorder",
                return_value=mock_recorder,
            ),
        ):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
            issues = analyzer.analyze_new_migrations()
            assert issues == []


class TestSquashedMigrations:
    """Tests for handling squashed/replaced migrations without KeyError."""

    def test_analyze_app_with_squashed_migrations(self, mock_migration_factory):
        """Test that analyze_app handles squashed migrations without crashing.

        When migrations are squashed, the old replaced migrations exist in
        disk_migrations but are removed from graph.nodes. Previously this
        caused a KeyError because get_migration() uses graph.nodes.
        """
        from unittest.mock import MagicMock, patch

        # Create a squash migration and the old replaced migrations
        old_mig = mock_migration_factory(
            [
                migrations.AddField(
                    model_name="user",
                    name="email",
                    field=models.CharField(max_length=255, null=True),
                )
            ],
            app_label="testapp",
            name="0001_initial",
        )
        squash_mig = mock_migration_factory(
            [
                migrations.AddField(
                    model_name="user",
                    name="email",
                    field=models.CharField(max_length=255, null=True),
                )
            ],
            app_label="testapp",
            name="0002_squashed",
        )
        squash_mig.replaces = [("testapp", "0001_initial")]

        # disk_migrations has BOTH old and squash (both exist on disk)
        disk = {
            ("testapp", "0001_initial"): old_mig,
            ("testapp", "0002_squashed"): squash_mig,
        }

        mock_loader = MagicMock()
        mock_loader.disk_migrations = disk
        # graph.nodes only has the squash (old was removed by Django)
        mock_loader.graph.nodes = {("testapp", "0002_squashed"): squash_mig}
        mock_loader.migrated_apps = {"testapp"}

        with patch(
            "django.db.migrations.loader.MigrationLoader",
            return_value=mock_loader,
        ):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
            # Should NOT raise KeyError
            issues = analyzer.analyze_app("testapp")
            assert isinstance(issues, list)

    def test_analyze_new_migrations_with_squashed_migrations(
        self, mock_migration_factory
    ):
        """Test that analyze_new_migrations handles squashed migrations."""
        from unittest.mock import MagicMock, patch

        old_mig = mock_migration_factory(
            [
                migrations.AddField(
                    model_name="user",
                    name="email",
                    field=models.CharField(max_length=255, null=True),
                )
            ],
            app_label="testapp",
            name="0001_initial",
        )
        squash_mig = mock_migration_factory(
            [
                migrations.AddField(
                    model_name="user",
                    name="email",
                    field=models.CharField(max_length=255, null=True),
                )
            ],
            app_label="testapp",
            name="0002_squashed",
        )
        squash_mig.replaces = [("testapp", "0001_initial")]

        disk = {
            ("testapp", "0001_initial"): old_mig,
            ("testapp", "0002_squashed"): squash_mig,
        }

        mock_loader = MagicMock()
        mock_loader.disk_migrations = disk
        mock_loader.graph.nodes = {("testapp", "0002_squashed"): squash_mig}

        mock_recorder = MagicMock()
        mock_recorder.applied_migrations.return_value = set()

        with (
            patch(
                "django.db.migrations.loader.MigrationLoader",
                return_value=mock_loader,
            ),
            patch(
                "django.db.migrations.recorder.MigrationRecorder",
                return_value=mock_recorder,
            ),
        ):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
            # Should NOT raise KeyError
            issues = analyzer.analyze_new_migrations()
            assert isinstance(issues, list)


class TestSeverityOverrides:
    """Tests for severity overrides via Django settings."""

    @override_settings(
        SAFE_MIGRATIONS={
            "RULE_SEVERITY": {"SM002": "INFO"},
            "EXCLUDED_APPS": [],
        }
    )
    def test_severity_override_downgrades_to_info(self, mock_migration_factory):
        """Test that RULE_SEVERITY overrides change issue severity."""
        from django_safe_migrations.rules.base import Severity

        operation = migrations.RemoveField(
            model_name="user",
            name="old_field",
        )
        migration = mock_migration_factory([operation])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        sm002_issues = [i for i in issues if i.rule_id == "SM002"]
        assert len(sm002_issues) == 1
        assert sm002_issues[0].severity == Severity.INFO

    def test_severity_default_without_override(self, mock_migration_factory):
        """Test that SM002 uses default severity without override."""
        from django_safe_migrations.rules.base import Severity

        operation = migrations.RemoveField(
            model_name="user",
            name="old_field",
        )
        migration = mock_migration_factory([operation])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        sm002_issues = [i for i in issues if i.rule_id == "SM002"]
        assert len(sm002_issues) == 1
        assert sm002_issues[0].severity == Severity.WARNING

    @override_settings(
        SAFE_MIGRATIONS={
            "RULE_SEVERITY": {"SM001": "WARNING"},
            "EXCLUDED_APPS": [],
        }
    )
    def test_severity_override_downgrades_error_to_warning(
        self, mock_migration_factory
    ):
        """Test that an error rule can be downgraded to warning."""
        from django_safe_migrations.rules.base import Severity

        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        migration = mock_migration_factory([operation])

        analyzer = MigrationAnalyzer(db_vendor="postgresql")
        issues = analyzer.analyze_migration(migration)

        sm001_issues = [i for i in issues if i.rule_id == "SM001"]
        assert len(sm001_issues) == 1
        assert sm001_issues[0].severity == Severity.WARNING
