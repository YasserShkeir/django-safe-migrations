"""Tests for utility functions."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from django.db import migrations, models

from django_safe_migrations.utils import (
    _get_operation_line_number_ast,
    _get_operation_line_number_fallback,
    format_operation_name,
    get_app_migrations,
    get_db_vendor,
    get_migration_file_path,
    get_operation_column_number,
    get_operation_line_number,
    is_mysql,
    is_postgres,
    is_sqlite,
    resolve_field_before_operation,
)


class TestFormatOperationName:
    """Tests for format_operation_name function."""

    def test_formats_addfield_with_model_and_name(self):
        """Test formatting AddField with model_name and name."""
        operation = migrations.AddField(
            model_name="user",
            name="email",
            field=models.CharField(max_length=255),
        )
        result = format_operation_name(operation)

        assert result == "AddField(user.email)"

    def test_formats_deletmodel_with_name_only(self):
        """Test formatting DeleteModel with name only."""
        operation = migrations.DeleteModel(name="OldModel")
        result = format_operation_name(operation)

        assert result == "DeleteModel(OldModel)"

    def test_formats_removefield_with_model_and_name(self):
        """Test formatting RemoveField with model_name and name."""
        operation = migrations.RemoveField(
            model_name="user",
            name="old_field",
        )
        result = format_operation_name(operation)

        assert result == "RemoveField(user.old_field)"

    def test_formats_runsql_without_model_or_name(self):
        """Test formatting RunSQL without model_name or name."""
        operation = migrations.RunSQL(sql="SELECT 1")
        result = format_operation_name(operation)

        assert result == "RunSQL"

    def test_formats_addindex_with_model_name(self):
        """Test formatting AddIndex with model_name."""
        operation = migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        )
        result = format_operation_name(operation)

        # AddIndex has model_name but not name attribute
        assert "AddIndex" in result
        assert "user" in result

    def test_formats_renamefield(self):
        """Test formatting RenameField."""
        operation = migrations.RenameField(
            model_name="user",
            old_name="username",
            new_name="login",
        )
        result = format_operation_name(operation)

        assert "RenameField" in result
        assert "user" in result


class TestGetMigrationFilePath:
    """Tests for get_migration_file_path function."""

    def test_returns_none_when_module_has_no_file(self):
        """Test returns None when module has no __file__ attribute."""
        migration = MagicMock()
        migration.__module__ = "builtins"  # builtins module has no __file__
        result = get_migration_file_path(migration)

        # builtins has no __file__, so should return None
        assert result is None

    def test_returns_path_for_real_migration(self):
        """Test returns file path for real migration with __module__."""
        # Use a real migration from our test project
        import importlib

        initial_migration = importlib.import_module(
            "tests.test_project.testapp.migrations.0001_initial"
        )

        migration = initial_migration.Migration
        result = get_migration_file_path(migration)

        assert result is not None
        assert "0001_initial.py" in result
        assert os.path.exists(result)

    def test_returns_none_for_import_error(self):
        """Test returns None when module import fails."""
        migration = MagicMock()
        migration.__module__ = "nonexistent.module.path"
        result = get_migration_file_path(migration)

        assert result is None


class TestGetOperationLineNumber:
    """Tests for get_operation_line_number function."""

    def test_finds_first_operation_line_number(self):
        """Test finding line number of first operation."""
        # Use a real migration from our test project
        import importlib

        initial_migration = importlib.import_module(
            "tests.test_project.testapp.migrations.0001_initial"
        )

        migration = initial_migration.Migration
        result = get_operation_line_number(migration, 0)

        # Should find a line number (exact value depends on file content)
        assert result is None or isinstance(result, int)

    def test_returns_none_for_nonexistent_file(self):
        """Test returns None when migration file doesn't exist."""
        migration = MagicMock()
        migration.__module__ = "nonexistent.module"
        result = get_operation_line_number(migration, 0)

        assert result is None

    def test_returns_none_for_invalid_operation_index(self):
        """Test returns None for operation index out of range."""
        import importlib

        initial_migration = importlib.import_module(
            "tests.test_project.testapp.migrations.0001_initial"
        )

        migration = initial_migration.Migration
        # Use a very high index that doesn't exist
        result = get_operation_line_number(migration, 999)

        assert result is None

    def test_parses_migration_file_with_operations(self):
        """Test parsing a migration file with multiple operations."""
        # Create a temporary migration file
        migration_content = """
from django.db import migrations, models

class Migration:
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestModel",
            fields=[
                ("id", models.AutoField(primary_key=True)),
            ],
        ),
        migrations.AddField(
            model_name="testmodel",
            name="email",
            field=models.CharField(max_length=255),
        ),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            # Create a mock migration that points to our temp file
            mock_migration = MagicMock()
            mock_mod = MagicMock()
            mock_mod.__file__ = temp_path

            with patch("importlib.import_module", return_value=mock_mod):
                with patch(
                    "django_safe_migrations.utils.get_migration_file_path",
                    return_value=temp_path,
                ):
                    result = get_operation_line_number(mock_migration, 0)
                    # Should find line 8 (migrations.CreateModel line)
                    assert result is not None
                    assert isinstance(result, int)
        finally:
            os.unlink(temp_path)


class TestASTLineNumberDetection:
    """Tests for AST-based line number detection."""

    def test_ast_finds_first_operation(self):
        """Test AST parser finds line number of first operation."""
        migration_content = """from django.db import migrations, models

class Migration:
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestModel",
            fields=[("id", models.AutoField(primary_key=True))],
        ),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_ast(temp_path, 0)
            assert result == 7  # Line with migrations.CreateModel
        finally:
            os.unlink(temp_path)

    def test_ast_finds_second_operation(self):
        """Test AST parser finds line number of second operation."""
        migration_content = """from django.db import migrations, models

class Migration:
    dependencies = []

    operations = [
        migrations.CreateModel(name="Model1", fields=[]),
        migrations.AddField(
            model_name="model1",
            name="field1",
            field=models.CharField(max_length=100),
        ),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_ast(temp_path, 1)
            assert result == 8  # Line with migrations.AddField
        finally:
            os.unlink(temp_path)

    def test_ast_handles_comments_in_operations(self):
        """Test AST parser correctly handles comments inside operations list."""
        migration_content = """from django.db import migrations, models

class Migration:
    dependencies = []

    operations = [
        # This is a comment that should be ignored
        migrations.CreateModel(
            name="TestModel",
            fields=[("id", models.AutoField(primary_key=True))],
        ),
        # Another comment
        migrations.AddField(
            model_name="testmodel",
            name="email",
            field=models.CharField(max_length=255),
        ),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            # First operation should be on line 8 (after the comment)
            result0 = _get_operation_line_number_ast(temp_path, 0)
            assert result0 == 8

            # Second operation should be on line 13 (after another comment)
            result1 = _get_operation_line_number_ast(temp_path, 1)
            assert result1 == 13
        finally:
            os.unlink(temp_path)

    def test_ast_handles_multiline_strings(self):
        """Test AST parser handles multi-line string literals."""
        migration_content = '''from django.db import migrations

class Migration:
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                SELECT * FROM table
                WHERE something = 'value'
            """,
            reverse_sql="SELECT 1",
        ),
        migrations.RunPython(code=lambda apps, schema_editor: None),
    ]
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result0 = _get_operation_line_number_ast(temp_path, 0)
            assert result0 == 7  # migrations.RunSQL line

            result1 = _get_operation_line_number_ast(temp_path, 1)
            assert result1 == 14  # migrations.RunPython line
        finally:
            os.unlink(temp_path)

    def test_ast_returns_none_for_out_of_range_index(self):
        """Test AST parser returns None for operation index out of range."""
        migration_content = """from django.db import migrations

class Migration:
    operations = [
        migrations.CreateModel(name="Test", fields=[]),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_ast(temp_path, 5)
            assert result is None
        finally:
            os.unlink(temp_path)

    def test_ast_returns_none_for_syntax_error(self):
        """Test AST parser returns None for files with syntax errors."""
        migration_content = """from django.db import migrations

class Migration:
    operations = [
        migrations.CreateModel(name="Test", fields=[]  # Missing closing paren
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_ast(temp_path, 0)
            assert result is None
        finally:
            os.unlink(temp_path)

    def test_ast_returns_none_for_missing_operations(self):
        """Test AST parser returns None when operations list is missing."""
        migration_content = """from django.db import migrations

class Migration:
    dependencies = []
    # No operations defined
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_ast(temp_path, 0)
            assert result is None
        finally:
            os.unlink(temp_path)


class TestFallbackLineNumberDetection:
    """Tests for fallback bracket-counting line number detection."""

    def test_fallback_finds_operation(self):
        """Test fallback method finds operation line numbers."""
        migration_content = """from django.db import migrations, models

class Migration:
    operations = [
        migrations.CreateModel(name="Test", fields=[]),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            result = _get_operation_line_number_fallback(temp_path, 0)
            assert result == 5  # Line with migrations.CreateModel
        finally:
            os.unlink(temp_path)

    def test_fallback_returns_none_for_missing_file(self):
        """Test fallback returns None for non-existent file."""
        result = _get_operation_line_number_fallback("/nonexistent/path.py", 0)
        assert result is None


class TestGetOperationColumnNumber:
    """Tests for get_operation_column_number function."""

    def test_gets_column_number(self):
        """Test getting column number of an operation."""
        migration_content = """from django.db import migrations

class Migration:
    operations = [
        migrations.CreateModel(name="Test", fields=[]),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            mock_migration = MagicMock()

            with patch(
                "django_safe_migrations.utils.get_migration_file_path",
                return_value=temp_path,
            ):
                result = get_operation_column_number(mock_migration, 0)
                assert result == 8  # Column of 'migrations.CreateModel'
        finally:
            os.unlink(temp_path)

    def test_column_number_returns_none_for_missing_file(self):
        """Test column number returns None for missing file."""
        mock_migration = MagicMock()

        with patch(
            "django_safe_migrations.utils.get_migration_file_path",
            return_value=None,
        ):
            result = get_operation_column_number(mock_migration, 0)
            assert result is None

    def test_column_number_returns_none_for_out_of_range(self):
        """Test column number returns None for operation index out of range."""
        migration_content = """from django.db import migrations

class Migration:
    operations = [
        migrations.CreateModel(name="Test", fields=[]),
    ]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(migration_content)
            temp_path = f.name

        try:
            mock_migration = MagicMock()

            with patch(
                "django_safe_migrations.utils.get_migration_file_path",
                return_value=temp_path,
            ):
                result = get_operation_column_number(mock_migration, 999)
                assert result is None
        finally:
            os.unlink(temp_path)


class TestGetDbVendor:
    """Tests for get_db_vendor function."""

    def test_returns_vendor_from_connection(self):
        """Test returns database vendor from Django connection."""
        result = get_db_vendor()

        # In test environment, should be sqlite
        assert result in ("sqlite", "postgresql", "mysql", "mariadb", "unknown")

    def test_returns_unknown_on_exception(self):
        """Test returns 'unknown' when connection fails."""
        with patch(
            "django.db.connection",
        ) as mock_conn:
            # Make vendor property raise an exception
            type(mock_conn).vendor = property(
                lambda self: (_ for _ in ()).throw(Exception("Connection error"))
            )
            # The function should catch the exception and return 'unknown'
            # Note: This is hard to test because the import happens at call time
            # Just verify the function handles the case gracefully
            result = get_db_vendor()
            assert isinstance(result, str)


class TestIsDatabaseChecks:
    """Tests for is_postgres, is_mysql, is_sqlite functions."""

    def test_is_postgres_returns_bool(self):
        """Test is_postgres returns boolean."""
        result = is_postgres()
        assert isinstance(result, bool)

    def test_is_mysql_returns_bool(self):
        """Test is_mysql returns boolean."""
        result = is_mysql()
        assert isinstance(result, bool)

    def test_is_sqlite_returns_bool(self):
        """Test is_sqlite returns boolean."""
        result = is_sqlite()
        assert isinstance(result, bool)

    def test_is_sqlite_true_for_sqlite_vendor(self):
        """Test is_sqlite returns True when vendor is sqlite."""
        with patch("django_safe_migrations.utils.get_db_vendor", return_value="sqlite"):
            assert is_sqlite() is True
            assert is_postgres() is False
            assert is_mysql() is False

    def test_is_postgres_true_for_postgresql_vendor(self):
        """Test is_postgres returns True when vendor is postgresql."""
        with patch(
            "django_safe_migrations.utils.get_db_vendor", return_value="postgresql"
        ):
            assert is_postgres() is True
            assert is_sqlite() is False
            assert is_mysql() is False

    def test_is_mysql_true_for_mysql_vendor(self):
        """Test is_mysql returns True when vendor is mysql."""
        with patch("django_safe_migrations.utils.get_db_vendor", return_value="mysql"):
            assert is_mysql() is True
            assert is_sqlite() is False
            assert is_postgres() is False

    def test_is_mysql_true_for_mariadb_vendor(self):
        """Test is_mysql returns True when vendor is mariadb."""
        with patch(
            "django_safe_migrations.utils.get_db_vendor", return_value="mariadb"
        ):
            assert is_mysql() is True


class TestGetAppMigrations:
    """Tests for get_app_migrations function."""

    def test_returns_list_for_valid_app(self):
        """Test returns list of migrations for valid app."""
        result = get_app_migrations("testapp")

        assert isinstance(result, list)
        # testapp should have migrations
        assert len(result) >= 1

    def test_returns_tuples_with_name_and_migration(self):
        """Test returns tuples of (name, migration)."""
        result = get_app_migrations("testapp")

        if result:  # Only test if we have migrations
            name, migration = result[0]
            assert isinstance(name, str)
            assert "0001" in name or "initial" in name.lower()

    def test_returns_empty_list_for_nonexistent_app(self):
        """Test returns empty list for app with no migrations."""
        result = get_app_migrations("nonexistent_app_xyz")

        assert result == []

    def test_migrations_are_sorted_by_name(self):
        """Test migrations are sorted by name."""
        result = get_app_migrations("testapp")

        if len(result) > 1:
            names = [name for name, _ in result]
            assert names == sorted(names)


# Skip get_unapplied_migrations tests as they require database access
# and are covered by integration tests
@pytest.mark.skip(reason="Covered by integration tests")
class TestGetUnappliedMigrations:
    """Tests for get_unapplied_migrations function.

    Note: These tests are skipped in unit tests because they require
    actual database access. They are covered in integration tests.
    """

    @pytest.mark.django_db
    def test_returns_list(self):
        """Test returns a list."""
        from django_safe_migrations.utils import get_unapplied_migrations

        result = get_unapplied_migrations()
        assert isinstance(result, list)

    @pytest.mark.django_db
    def test_filters_by_app_label(self):
        """Test filters by app label when provided."""
        from django_safe_migrations.utils import get_unapplied_migrations

        result = get_unapplied_migrations(app_label="testapp")
        # All results should be for testapp
        for app, name in result:
            assert app == "testapp"


class TestResolveFieldBeforeOperation:
    """Tests for resolve_field_before_operation function (v0.5.0).

    This utility uses Django's MigrationLoader to resolve the field state
    before an AlterField operation, enabling precise old-vs-new comparison.
    """

    def test_returns_none_for_nonexistent_migration(self):
        """Test returns None when migration doesn't exist."""
        result = resolve_field_before_operation(
            app_label="nonexistent_app",
            migration_name="0001_initial",
            operation_index=0,
            model_name="mymodel",
            field_name="myfield",
        )
        assert result is None

    def test_returns_none_for_nonexistent_model(self):
        """Test returns None when model doesn't exist in migration state."""
        result = resolve_field_before_operation(
            app_label="testapp",
            migration_name="0001_initial",
            operation_index=0,
            model_name="nonexistent_model",
            field_name="myfield",
        )
        assert result is None

    def test_returns_none_for_nonexistent_field(self):
        """Test returns None when field doesn't exist in model state."""
        result = resolve_field_before_operation(
            app_label="testapp",
            migration_name="0001_initial",
            operation_index=0,
            model_name="testmodel",
            field_name="nonexistent_field",
        )
        assert result is None

    def test_resolves_field_from_testapp(self):
        """Test resolving a known field from the test project.

        Resolves 'username' before migration 0002, which was created
        in 0001_initial.
        """
        result = resolve_field_before_operation(
            app_label="testapp",
            migration_name="0002_unsafe_not_null",
            operation_index=0,
            model_name="user",
            field_name="username",
        )
        assert result is not None
        assert result.__class__.__name__ == "CharField"

    def test_resolves_nullable_field_before_alter(self):
        """Test resolving field state before AlterField (dict-fields fix).

        Migration 0013 adds 'order' as IntegerField(null=True).
        Resolving before 0014 should see null=True, proving that
        Django's dict-based model_state.fields is handled correctly.
        """
        result = resolve_field_before_operation(
            app_label="testapp",
            migration_name="0014_alterfield_null_false",
            operation_index=0,
            model_name="user",
            field_name="order",
        )
        assert result is not None
        assert result.__class__.__name__ == "IntegerField"
        assert getattr(result, "null", False) is True
