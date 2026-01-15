"""Django Safe Migrations.

Detect unsafe Django migrations before they break production.
"""

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.rules.base import Issue, Severity

__version__ = "0.1.1"
__all__ = [
    "MigrationAnalyzer",
    "Issue",
    "Severity",
    "__version__",
]

default_app_config = "django_safe_migrations.apps.DjangoSafeMigrationsConfig"
