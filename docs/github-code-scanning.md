# GitHub Code Scanning Integration

Django Safe Migrations can output results in [SARIF](https://sarifweb.azurewebsites.net/) (Static Analysis Results Interchange Format), which is supported by GitHub Code Scanning.

## What is GitHub Code Scanning?

GitHub Code Scanning is a feature that analyzes code in your repository to find security vulnerabilities and errors. With SARIF integration, django-safe-migrations results appear:

- In the **Security** tab of your repository
- As inline **PR annotations**
- In the security dashboard for **tracking over time**

## Quick Setup

### 1. Create the Workflow

Add this workflow to `.github/workflows/migration-check.yml`:

```yaml
name: Migration Safety Check

on:
  push:
    branches: [main]
    paths:
      - '**/migrations/**'
  pull_request:
    paths:
      - '**/migrations/**'

jobs:
  check-migrations:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write  # Required for SARIF upload

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install django-safe-migrations Django
          # Install your project dependencies if needed
          # pip install -r requirements.txt

      - name: Run migration check
        run: |
          python manage.py check_migrations --format=sarif --output=results.sarif
        continue-on-error: true  # Don't fail here, let SARIF upload handle it

      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
          category: django-safe-migrations
```

### 2. Enable Code Scanning

1. Go to your repository's **Settings** > **Code security and analysis**
2. Enable **Code scanning**
3. The next push will trigger the workflow

### 3. View Results

After the workflow runs, you can view results:

- **Security tab**: Repository → Security → Code scanning alerts
- **Pull requests**: Inline annotations on changed files
- **Checks**: In the PR checks list

## SARIF Output Format

The SARIF output includes:

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "django-safe-migrations",
        "version": "0.2.0",
        "rules": [
          {
            "id": "SM001",
            "name": "NotNullWithoutDefaultRule",
            "shortDescription": { "text": "Adding NOT NULL column without default" },
            "helpUri": "https://django-safe-migrations.readthedocs.io/en/latest/rules/SM001/"
          }
        ]
      }
    },
    "results": [
      {
        "ruleId": "SM001",
        "level": "error",
        "message": { "text": "Adding NOT NULL field 'email' without a default" },
        "locations": [{
          "physicalLocation": {
            "artifactLocation": { "uri": "myapp/migrations/0002_add_email.py" },
            "region": { "startLine": 15 }
          }
        }]
      }
    ]
  }]
}
```

## Severity Mapping

| django-safe-migrations | SARIF Level | GitHub Display |
| ---------------------- | ----------- | -------------- |
| ERROR                  | `error`     | 🔴 Error       |
| WARNING                | `warning`   | 🟡 Warning     |
| INFO                   | `note`      | 🔵 Note        |

## Command Options

### Basic SARIF Output

```bash
# Output to stdout
python manage.py check_migrations --format=sarif

# Output to file
python manage.py check_migrations --format=sarif --output=results.sarif
python manage.py check_migrations --format=sarif -o results.sarif
```

### Combining with Other Options

```bash
# Check only new migrations, output SARIF
python manage.py check_migrations --new-only --format=sarif -o results.sarif

# Exclude apps
python manage.py check_migrations --format=sarif -o results.sarif --exclude-apps legacy_app
```

## Example Workflow: Full CI Pipeline

A complete workflow that runs tests and checks migrations:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest

  migration-check:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check migrations
        run: python manage.py check_migrations --format=sarif -o results.sarif
        continue-on-error: true

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

## Dismissing Alerts

When you've reviewed an alert and determined it's safe, you can dismiss it in GitHub:

1. Go to Security → Code scanning alerts
2. Click on the alert
3. Click "Dismiss alert"
4. Choose a reason:
   - **False positive** - The warning doesn't apply
   - **Won't fix** - Intentional pattern
   - **Used in tests** - Test code only

## Filtering by Rule

In the Security tab, you can filter alerts by rule:

- `tool:django-safe-migrations rule:SM001` - Only SM001 alerts
- `is:open tool:django-safe-migrations` - All open alerts

## Programmatic SARIF Generation

You can also generate SARIF programmatically:

```python
from django_safe_migrations import MigrationAnalyzer
from django_safe_migrations.reporters import SarifReporter

analyzer = MigrationAnalyzer()
issues = analyzer.analyze_all()

reporter = SarifReporter()
sarif_output = reporter.report(issues)

# Write to file
with open('results.sarif', 'w') as f:
    f.write(sarif_output)
```

## Troubleshooting

### SARIF Upload Fails

Ensure you have the correct permissions in your workflow:

```yaml
permissions:
  contents: read
  security-events: write
```

### No Alerts Appearing

1. Check if Code Scanning is enabled in repository settings
2. Verify the SARIF file was generated correctly
3. Check the workflow logs for errors

### False Positives

Use [inline suppression comments](configuration.md#inline-suppression-comments) to suppress intentional warnings:

```python
# safe-migrations: ignore SM001 -- adding nullable first
migrations.AddField(...)
```
