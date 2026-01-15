"""Safe app with only safe migrations for testing."""

from django.apps import AppConfig


class SafeAppConfig(AppConfig):
    """Config for safeapp."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.test_project.safeapp"
    label = "safeapp"
