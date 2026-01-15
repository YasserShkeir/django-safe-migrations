"""Test app with intentionally unsafe migrations for testing."""

from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """Config for testapp."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.test_project.testapp"
    label = "testapp"
