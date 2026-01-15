# Django Safe Migrations

Detect unsafe Django migrations before they break production.

## What is Django Safe Migrations?

Django Safe Migrations is a static analysis tool for Django migrations. It scans your migrations and warns you about operations that could cause:

- **Table locks** that block reads/writes
- **Downtime** during deployments
- **Data loss** from unsafe drops
- **Application errors** from schema/code mismatches

## Quick Example

```bash
$ python manage.py check_migrations

Found 1 migration issue(s):

✖ ERROR [SM001] myapp/migrations/0002_add_email.py:15
   Adding NOT NULL field 'email' to 'user' without a default value will lock the table
   Operation: AddField(user.email)

   💡 Suggestion:
      1. Add field as nullable first
      2. Backfill existing rows
      3. Add NOT NULL constraint in separate migration
```

## Why Use This?

| Without Safe Migrations                         | With Safe Migrations       |
| ----------------------------------------------- | -------------------------- |
| Deploy, find out table is locked for 10 minutes | Get warned before merge    |
| Roll back, scramble to fix                      | Fix with suggested pattern |
| Angry users, lost revenue                       | Happy users, smooth deploy |

## Features

- 🔍 **5+ built-in rules** for common issues
- 🐘 **PostgreSQL-aware** (concurrent indexes, etc.)
- 💡 **Fix suggestions** with safe patterns
- 🔧 **CI/CD ready** (GitHub Actions, JSON output)
- ⚡ **Fast** - analyzes migrations without running them

## Getting Started

```bash
pip install django-safe-migrations
```

Then check out the [Installation](installation.md) and [Quick Start](quickstart.md) guides.
