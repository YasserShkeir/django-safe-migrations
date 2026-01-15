"""MySQL settings for testing."""

import os

from tests.test_project.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DB", "test_db"),
        "USER": os.environ.get("MYSQL_USER", "test_user"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "test_password"),
        "HOST": os.environ.get("MYSQL_HOST", "localhost"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
    }
}
