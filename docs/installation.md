# Installation

## Requirements

- Python 3.9+
- Django 3.2+

## Install from PyPI

```bash
pip install django-safe-migrations
```

### With PostgreSQL support

If you're using PostgreSQL and want to run integration tests:

```bash
pip install django-safe-migrations[postgres]
```

## Add to Django

Add `django_safe_migrations` to your `INSTALLED_APPS`:

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Add this
    'django_safe_migrations',

    # Your apps
    'myapp',
]
```

## Verify Installation

Run the management command:

```bash
python manage.py check_migrations --help
```

You should see:

```
usage: manage.py check_migrations [-h] [--format {console,json,github}]
                                  [--fail-on-warning] [--new-only]
                                  [--no-suggestions] [--exclude-apps ...]
                                  [--include-django-apps]
                                  [app_labels ...]

Check migrations for unsafe operations
...
```

## Development Installation

For contributing or development:

```bash
git clone https://github.com/YasserShkeir/django-safe-migrations.git
cd django-safe-migrations
pip install -e ".[dev]"
pre-commit install
```
