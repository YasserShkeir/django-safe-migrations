"""Django app configuration for django-safe-migrations."""

from django.apps import AppConfig


class DjangoSafeMigrationsConfig(AppConfig):
    """App configuration for Django Safe Migrations."""

    name = "django_safe_migrations"
    verbose_name = "Django Safe Migrations"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register the (opt-in) migration-safety system check."""
        from django.core.checks import register

        from django_safe_migrations.checks import check_migration_safety

        register(check_migration_safety, "migrations")
