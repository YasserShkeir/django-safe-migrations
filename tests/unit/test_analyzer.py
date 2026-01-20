"""Tests for the MigrationAnalyzer."""

from django.db import migrations, models

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
