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

### Basic Setup

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

### With PostgreSQL Service

```yaml
# .gitlab-ci.yml
check-migrations:
  image: python:3.12
  stage: test
  services:
    - postgres:15-alpine
  variables:
    POSTGRES_DB: test_db
    POSTGRES_USER: test_user
    POSTGRES_PASSWORD: test_pass
    DATABASE_URL: postgres://test_user:test_pass@postgres:5432/test_db
  script:
    - pip install django-safe-migrations[postgres]
    - pip install -r requirements.txt
    - python manage.py check_migrations --format=json --fail-on-warning
  artifacts:
    when: always
    reports:
      codequality: migration-report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - "**/migrations/**"
        - "**/models.py"
```

### SARIF Output for GitLab SAST

```yaml
# .gitlab-ci.yml
check-migrations-sast:
  image: python:3.12
  stage: test
  script:
    - pip install django-safe-migrations
    - pip install -r requirements.txt
    - python manage.py check_migrations --format=sarif --output=gl-sast-report.json
  artifacts:
    reports:
      sast: gl-sast-report.json
  allow_failure: true
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

### Basic Declarative Pipeline

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

### With Docker and PostgreSQL

```groovy
// Jenkinsfile
pipeline {
    agent {
        docker {
            image 'python:3.12'
        }
    }

    environment {
        DATABASE_URL = 'postgres://postgres:postgres@postgres:5432/test_db'
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    pip install django-safe-migrations[postgres]
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Check Migrations') {
            steps {
                script {
                    def result = sh(
                        script: 'python manage.py check_migrations --format=json',
                        returnStatus: true
                    )
                    if (result != 0) {
                        unstable('Migration safety issues detected')
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'migration-report.json', allowEmptyArchive: true
        }
    }
}
```

### Warnings Plugin Integration

```groovy
// Jenkinsfile - with Warnings Next Generation plugin
pipeline {
    agent any

    stages {
        stage('Check Migrations') {
            steps {
                sh '''
                    pip install django-safe-migrations
                    pip install -r requirements.txt
                    python manage.py check_migrations --format=json > migration-issues.json || true
                '''
            }
            post {
                always {
                    recordIssues(
                        tools: [issues(pattern: 'migration-issues.json', name: 'Migration Safety')]
                    )
                }
            }
        }
    }
}
```

## Azure Pipelines

### Basic Setup

```yaml
# azure-pipelines.yml
trigger:
  paths:
    include:
      - '**/migrations/**'
      - '**/models.py'

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.12'

  - script: |
      pip install django-safe-migrations
      pip install -r requirements.txt
    displayName: 'Install dependencies'

  - script: |
      python manage.py check_migrations --format=json > $(Build.ArtifactStagingDirectory)/migration-report.json
    displayName: 'Check migrations'

  - task: PublishBuildArtifacts@1
    inputs:
      pathToPublish: '$(Build.ArtifactStagingDirectory)/migration-report.json'
      artifactName: 'migration-report'
    condition: always()
```

### With PostgreSQL Service Container

```yaml
# azure-pipelines.yml
trigger:
  paths:
    include:
      - '**/migrations/**'

pool:
  vmImage: 'ubuntu-latest'

services:
  postgres:
    image: postgres:15
    ports:
      - 5432:5432
    env:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass

variables:
  DATABASE_URL: 'postgres://test_user:test_pass@localhost:5432/test_db'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.12'

  - script: |
      pip install django-safe-migrations[postgres]
      pip install -r requirements.txt
    displayName: 'Install dependencies'

  - script: |
      python manage.py check_migrations --fail-on-warning
    displayName: 'Check migrations'
```

### PR Validation with Comments

```yaml
# azure-pipelines.yml
trigger: none

pr:
  paths:
    include:
      - '**/migrations/**'

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.12'

  - script: |
      pip install django-safe-migrations
      pip install -r requirements.txt
    displayName: 'Install dependencies'

  - script: |
      python manage.py check_migrations --format=json > migration-report.json
    displayName: 'Check migrations'
    continueOnError: true

  - task: PublishPipelineArtifact@1
    inputs:
      targetPath: 'migration-report.json'
      artifact: 'MigrationReport'
    condition: always()

  # Optional: Post results as PR comment using Azure DevOps API
  - script: |
      if [ -f migration-report.json ]; then
        ISSUES=$(cat migration-report.json | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('total', 0))")
        if [ "$ISSUES" -gt 0 ]; then
          echo "##vso[task.logissue type=warning]Found $ISSUES migration safety issues"
        fi
      fi
    displayName: 'Report results'
```

## Bitbucket Pipelines

```yaml
# bitbucket-pipelines.yml
image: python:3.12

pipelines:
  pull-requests:
    '**':
      - step:
          name: Check Migrations
          caches:
            - pip
          script:
            - pip install django-safe-migrations
            - pip install -r requirements.txt
            - python manage.py check_migrations --format=json > migration-report.json
          artifacts:
            - migration-report.json
          condition:
            changesets:
              includePaths:
                - '**/migrations/**'
                - '**/models.py'
```

### With PostgreSQL

```yaml
# bitbucket-pipelines.yml
image: python:3.12

definitions:
  services:
    postgres:
      image: postgres:15
      environment:
        POSTGRES_DB: test_db
        POSTGRES_USER: test_user
        POSTGRES_PASSWORD: test_pass

pipelines:
  pull-requests:
    '**':
      - step:
          name: Check Migrations
          services:
            - postgres
          script:
            - pip install django-safe-migrations[postgres]
            - pip install -r requirements.txt
            - export DATABASE_URL=postgres://test_user:test_pass@localhost:5432/test_db
            - python manage.py check_migrations --fail-on-warning
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
