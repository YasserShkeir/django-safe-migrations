"""Tests that the package version stays consistent across sources.

Guards against the version desync where pyproject.toml and
``django_safe_migrations.__version__`` drift apart (e.g. 0.6.0 vs 0.5.2),
which silently mislabels the SARIF reporter's tool driver version.
"""

from __future__ import annotations

import re
from pathlib import Path

import django_safe_migrations

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _pyproject_version() -> str:
    """Read the project version from pyproject.toml.

    Uses tomllib on Python 3.11+ and falls back to a simple regex on
    older interpreters so the test runs across the full support matrix.
    """
    try:
        import tomllib  # type: ignore[import-not-found]

        with PYPROJECT.open("rb") as fh:
            return str(tomllib.load(fh)["project"]["version"])
    except ModuleNotFoundError:
        text = PYPROJECT.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        assert match, "Could not find version in pyproject.toml"
        return match.group(1)


def test_package_version_matches_pyproject() -> None:
    """__version__ must equal the version declared in pyproject.toml."""
    assert django_safe_migrations.__version__ == _pyproject_version()
