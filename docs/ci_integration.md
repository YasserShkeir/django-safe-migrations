# CI/CD Integration

Integrate Django Safe Migrations into your CI/CD pipeline to catch unsafe migrations before they're merged.

## GitHub Actions

### Basic Setup

Create `.github/workflows/check-migrations.yml`:

```yaml
name: Check Migrations

on:
  pull_request:
    paths:
      - "**/migrations/**"
      - "**models.py"

jobs:
  check-migrations:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install django-safe-migrations
          pip install -r requirements.txt  # Your project dependencies

      - name: Check migrations
        run: python manage.py check_migrations --format=github
```

### With PostgreSQL

For PostgreSQL-specific rules:

```yaml
name: Check Migrations

on:
  pull_request:
    paths:
      - "**/migrations/**"

jobs:
  check-migrations:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/test_db

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install django-safe-migrations[postgres]
          pip install -r requirements.txt

      - name: Check migrations
        run: python manage.py check_migrations --format=github --fail-on-warning
```

### GitHub Annotations

Using `--format=github` creates annotations that appear directly in your pull request files view and check runs.

## GitLab CI

```yaml
# .gitlab-ci.yml
check-migrations:
  image: python:3.12
  stage: test
  script:
    - pip install django-safe-migrations
    - pip install -r requirements.txt
    - python manage.py check_migrations --format=json > migration-report.json
  artifacts:
    reports:
      codequality: migration-report.json
  only:
    changes:
      - "**/migrations/**"
```

## CircleCI

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  check-migrations:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: |
            pip install django-safe-migrations
            pip install -r requirements.txt
      - run:
          name: Check migrations
          command: python manage.py check_migrations

workflows:
  version: 2
  test:
    jobs:
      - check-migrations
```

## Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any

    stages {
        stage('Check Migrations') {
            steps {
                sh '''
                    pip install django-safe-migrations
                    pip install -r requirements.txt
                    python manage.py check_migrations --format=json > migration-report.json
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'migration-report.json'
                }
            }
        }
    }
}
```

## JSON Output

For programmatic processing, use JSON output:

```bash
python manage.py check_migrations --format=json
```

Output:

```json
{
  "total": 2,
  "issues": [
    {
      "rule_id": "SM001",
      "severity": "error",
      "operation": "AddField(user.email)",
      "message": "Adding NOT NULL field 'email' without default",
      "file_path": "myapp/migrations/0002_add_email.py",
      "line_number": 15
    }
  ],
  "summary": {
    "errors": 1,
    "warnings": 1,
    "by_rule": { "SM001": 1, "SM002": 1 }
  }
}
```
