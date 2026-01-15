.PHONY: help install install-dev test test-cov lint format typecheck clean build release ci-check

PYTHON ?= python
VERSION ?= $(shell $(PYTHON) -c "from django_safe_migrations import __version__; print(__version__)")

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	$(PYTHON) -m pip install -e .

install-dev:  ## Install package with dev dependencies
	$(PYTHON) -m pip install -e ".[dev,docs]"
	pre-commit install

test:  ## Run tests
	pytest tests -v

test-cov:  ## Run tests with coverage
	pytest tests -v --cov=django_safe_migrations --cov-report=html --cov-report=term-missing

test-parallel:  ## Run tests in parallel
	pytest tests -n auto -v

lint:  ## Run linters
	black --check django_safe_migrations tests
	isort --check-only django_safe_migrations tests
	flake8 django_safe_migrations tests
	bandit -r django_safe_migrations -c pyproject.toml

format:  ## Format code
	black django_safe_migrations tests
	isort django_safe_migrations tests

typecheck:  ## Run type checker
	mypy django_safe_migrations

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .coverage htmlcov/ .tox/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean  ## Build package
	$(PYTHON) -m build

release: build  ## Release to PyPI (usage: make release VERSION=x.y.z)
	@echo "Releasing version $(VERSION)"
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin v$(VERSION)
	$(PYTHON) -m twine upload dist/*

ci-check: lint typecheck test  ## Run all CI checks

ci-check-fast: lint  ## Run quick CI checks (lint only)
	pytest tests -x -q

tox:  ## Run tox for all environments
	tox

tox-parallel:  ## Run tox in parallel
	tox -p auto

docs:  ## Build documentation
	mkdocs build

docs-serve:  ## Serve documentation locally
	mkdocs serve
