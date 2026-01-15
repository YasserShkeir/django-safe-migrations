"""Django app configuration for django-safe-migrations."""

from django.apps import AppConfig


class DjangoSafeMigrationsConfig(AppConfig):
    """App configuration for Django Safe Migrations."""

    name = "django_safe_migrations"
    verbose_name = "Django Safe Migrations"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Perform initialization when the app is ready."""
        pass
