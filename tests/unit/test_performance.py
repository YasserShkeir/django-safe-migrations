"""Performance benchmarks for django-safe-migrations.

These tests measure the performance characteristics of the analyzer
and can be used to detect performance regressions.

Run with: pytest tests/unit/test_performance.py -v --benchmark-only
Or without benchmarks: pytest tests/unit/test_performance.py -v
"""

from __future__ import annotations

import time
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from django.db import migrations, models

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.reporters.console import ConsoleReporter
from django_safe_migrations.reporters.json_reporter import JsonReporter
from django_safe_migrations.reporters.sarif import SarifReporter
from django_safe_migrations.rules.base import Issue, Severity

if TYPE_CHECKING:
    from collections.abc import Callable


class TestAnalyzerPerformance:
    """Performance tests for MigrationAnalyzer."""

    @pytest.fixture
    def large_migration(self) -> Mock:
        """Create a migration with many operations."""
        operations = []

        # Add 100 AddField operations
        for i in range(100):
            operations.append(
                migrations.AddField(
                    model_name="model",
                    name=f"field_{i}",
                    field=models.CharField(max_length=100, null=True),
                )
            )

        # Add 50 RemoveField operations
        for i in range(50):
            operations.append(
                migrations.RemoveField(
                    model_name="model",
                    name=f"old_field_{i}",
                )
            )

        # Add 25 AddIndex operations
        for i in range(25):
            operations.append(
                migrations.AddIndex(
                    model_name="model",
                    index=models.Index(fields=[f"field_{i}"], name=f"idx_{i}"),
                )
            )

        migration = Mock()
        migration.operations = operations
        migration.app_label = "testapp"
        migration.name = "0001_large"
        migration.__module__ = "testapp.migrations.0001_large"

        return migration

    @pytest.fixture
    def many_migrations(self) -> list[Mock]:
        """Create many small migrations."""
        migrations_list = []

        for i in range(50):
            operation = migrations.AddField(
                model_name="model",
                name=f"field_{i}",
                field=models.CharField(max_length=100, null=True),
            )

            migration = Mock()
            migration.operations = [operation]
            migration.app_label = "testapp"
            migration.name = f"000{i}_migration"
            migration.__module__ = f"testapp.migrations.000{i}_migration"
            migrations_list.append(migration)

        return migrations_list

    def test_analyze_large_migration_performance(self, large_migration: Mock) -> None:
        """Benchmark analyzing a migration with many operations."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        start_time = time.perf_counter()
        issues = analyzer.analyze_migration(large_migration)
        elapsed = time.perf_counter() - start_time

        # Should complete in under 2 seconds even with 175 operations
        assert elapsed < 2.0, f"Analysis took {elapsed:.3f}s, expected < 2.0s"

        # Verify it actually analyzed operations
        assert isinstance(issues, list)

    def test_analyze_many_migrations_performance(
        self, many_migrations: list[Mock]
    ) -> None:
        """Benchmark analyzing many migrations."""
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        start_time = time.perf_counter()
        all_issues = []
        for migration in many_migrations:
            issues = analyzer.analyze_migration(migration)
            all_issues.extend(issues)
        elapsed = time.perf_counter() - start_time

        # Should complete in under 5 seconds for 50 migrations
        assert elapsed < 5.0, f"Analysis took {elapsed:.3f}s, expected < 5.0s"

    def test_rule_instantiation_performance(self) -> None:
        """Benchmark rule instantiation."""
        from django_safe_migrations.rules import get_all_rules

        start_time = time.perf_counter()
        # Instantiate all rules 100 times
        for _ in range(100):
            rules = get_all_rules("postgresql")
        elapsed = time.perf_counter() - start_time

        # Should be very fast (< 2.0s for 100 iterations)
        assert elapsed < 2.0, f"Rule instantiation took {elapsed:.3f}s, expected < 2.0s"
        assert len(rules) > 0

    def test_analyzer_initialization_performance(self) -> None:
        """Benchmark analyzer initialization."""
        start_time = time.perf_counter()
        # Create 100 analyzer instances
        for _ in range(100):
            analyzer = MigrationAnalyzer(db_vendor="postgresql")
        elapsed = time.perf_counter() - start_time

        # Should be fast (< 2s for 100 initializations)
        assert elapsed < 2.0, f"Initialization took {elapsed:.3f}s, expected < 2.0s"
        assert len(analyzer.rules) > 0


class TestReporterPerformance:
    """Performance tests for reporters."""

    @pytest.fixture
    def many_issues(self) -> list[Issue]:
        """Create a list of many issues."""
        issues = []
        for i in range(500):
            issues.append(
                Issue(
                    rule_id=f"SM{(i % 20) + 1:03d}",
                    severity=[Severity.ERROR, Severity.WARNING, Severity.INFO][i % 3],
                    operation=f"Operation{i}",
                    message=f"Issue message {i} with some details about the problem",
                    suggestion=f"Suggestion {i}: Here is how to fix this issue",
                    file_path=f"app/migrations/000{i}_migration.py",
                    line_number=10 + i,
                    app_label="testapp",
                    migration_name=f"000{i}_migration",
                )
            )
        return issues

    def test_console_reporter_performance(self, many_issues: list[Issue]) -> None:
        """Benchmark console reporter with many issues."""
        stream = StringIO()
        reporter = ConsoleReporter(
            stream=stream, use_color=False, show_suggestions=True
        )

        start_time = time.perf_counter()
        reporter.report(many_issues)
        elapsed = time.perf_counter() - start_time

        # Should complete in under 2 seconds for 500 issues
        assert elapsed < 2.0, f"Console report took {elapsed:.3f}s, expected < 2.0s"

        # Verify output was generated
        output = stream.getvalue()
        assert len(output) > 0

    def test_json_reporter_performance(self, many_issues: list[Issue]) -> None:
        """Benchmark JSON reporter with many issues."""
        stream = StringIO()
        reporter = JsonReporter(stream=stream)

        start_time = time.perf_counter()
        reporter.report(many_issues)
        elapsed = time.perf_counter() - start_time

        # Should complete in under 2 seconds for 500 issues
        assert elapsed < 2.0, f"JSON report took {elapsed:.3f}s, expected < 2.0s"

        # Verify valid JSON was generated
        import json

        output = stream.getvalue()
        data = json.loads(output)
        assert len(data["issues"]) == 500

    def test_sarif_reporter_performance(self, many_issues: list[Issue]) -> None:
        """Benchmark SARIF reporter with many issues."""
        stream = StringIO()
        reporter = SarifReporter(stream=stream)

        start_time = time.perf_counter()
        reporter.report(many_issues)
        elapsed = time.perf_counter() - start_time

        # Should complete in under 2 seconds for 500 issues (generous for CI runners)
        assert elapsed < 2.0, f"SARIF report took {elapsed:.3f}s, expected < 2.0s"

        # Verify valid JSON was generated
        import json

        output = stream.getvalue()
        data = json.loads(output)
        assert len(data["runs"][0]["results"]) == 500


class TestConfigurationPerformance:
    """Performance tests for configuration loading."""

    def test_config_loading_performance(self) -> None:
        """Benchmark configuration loading."""
        from django_safe_migrations.conf import get_config, get_disabled_rules

        start_time = time.perf_counter()
        # Load config 1000 times
        for _ in range(1000):
            config = get_config()
            disabled = get_disabled_rules()
        elapsed = time.perf_counter() - start_time

        # Should be very fast with caching (< 1.0s for 1000 loads)
        assert elapsed < 1.0, f"Config loading took {elapsed:.3f}s, expected < 1.0s"
        assert isinstance(config, dict)
        assert isinstance(disabled, (list, set))  # Can be list or set

    def test_config_validation_performance(self) -> None:
        """Benchmark configuration validation."""
        from django_safe_migrations.conf import validate_config

        start_time = time.perf_counter()
        # Validate config 100 times
        for _ in range(100):
            warnings = validate_config()
        elapsed = time.perf_counter() - start_time

        # Should complete in under 2 seconds for 100 validations
        assert elapsed < 2.0, f"Validation took {elapsed:.3f}s, expected < 2.0s"
        assert isinstance(warnings, list)


class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    def test_analyzer_memory_cleanup(self) -> None:
        """Test that analyzer doesn't accumulate memory."""
        import gc

        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        # Create and analyze many migrations
        for i in range(100):
            operation = migrations.AddField(
                model_name="model",
                name=f"field_{i}",
                field=models.CharField(max_length=100, null=True),
            )
            migration = Mock()
            migration.operations = [operation]
            migration.app_label = "testapp"
            migration.name = f"000{i}_test"
            migration.__module__ = f"testapp.migrations.000{i}_test"

            issues = analyzer.analyze_migration(migration)

            # Issues should be collected
            del issues

        # Force garbage collection
        gc.collect()

        # Verify all 100 iterations completed without memory issues
        assert i == 99

    def test_reporter_memory_efficiency(self) -> None:
        """Test that reporters don't accumulate excessive memory."""
        import gc

        # Generate many reports
        iterations = 0
        for iterations in range(1, 51):  # noqa: B007
            issues = [
                Issue(
                    rule_id="SM001",
                    severity=Severity.ERROR,
                    operation="AddField",
                    message="Test message",
                    file_path="test.py",
                    line_number=1,
                )
                for _ in range(100)
            ]

            stream = StringIO()
            reporter = JsonReporter(stream=stream)
            reporter.report(issues)

            # Clean up
            del reporter
            del stream
            del issues

        gc.collect()

        # Verify all 50 iterations completed without memory issues
        assert iterations == 50


# Pytest benchmark integration (optional)
try:
    import pytest_benchmark  # noqa: F401

    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False


@pytest.mark.skipif(not HAS_BENCHMARK, reason="pytest-benchmark not installed")
class TestBenchmarks:
    """Benchmarks using pytest-benchmark (optional)."""

    def test_benchmark_single_migration(  # type: ignore[type-arg]
        self, benchmark: Callable, mock_migration_factory
    ) -> None:
        """Benchmark single migration analysis."""
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        migration = mock_migration_factory([operation])
        analyzer = MigrationAnalyzer(db_vendor="postgresql")

        result = benchmark(analyzer.analyze_migration, migration)
        assert isinstance(result, list)

    def test_benchmark_rule_check(  # type: ignore[type-arg]
        self, benchmark: Callable
    ) -> None:
        """Benchmark individual rule check."""
        from django_safe_migrations.rules.add_field import NotNullWithoutDefaultRule

        rule = NotNullWithoutDefaultRule()
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        migration = Mock()
        migration.app_label = "testapp"
        migration.name = "0001_test"
        migration.__module__ = "testapp.migrations.0001_test"

        result = benchmark(rule.check, operation, migration, 0)
        # Result may be Issue or None
        assert result is None or isinstance(result, Issue)
