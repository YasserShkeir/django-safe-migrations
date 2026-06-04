"""Lint result caching.

Caches per-migration analysis results so unchanged migrations are not
re-analysed on subsequent runs. Opt-in via ``--cache`` / ``--cache-file``.

Correctness
-----------
Each migration's cache entry is keyed on a content hash that combines the
migration's own source file with the source files of its **transitive
dependencies** (its ``forwards_plan`` in the migration graph). This means an
``AlterField`` whose historical field state lives in an ancestor migration is
correctly invalidated whenever that ancestor changes — not just when the
migration's own file changes.

The whole cache is namespaced by a *fingerprint* of everything else that can
change a result: the package version, the active rule IDs, the database vendor,
the Django version, ``USE_TZ`` and a hash of the resolved configuration. A
fingerprint mismatch discards the entire cache, so upgrades / config changes
never serve stale results.

The cache is best-effort: any I/O or graph error degrades to "analyse normally"
rather than raising.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from django_safe_migrations.rules.base import Issue

logger = logging.getLogger("django_safe_migrations")

CACHE_VERSION = 1
DEFAULT_CACHE_FILE = ".dsm_cache.json"


def file_sha256(path: str) -> str:
    """Return the hex SHA-256 of a file's bytes (streamed)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_fingerprint(
    db_vendor: str,
    rule_ids: list[str],
    check_reverse: bool = False,
) -> str:
    """Compute a fingerprint that namespaces the cache.

    Any change to the things below must invalidate the entire cache because
    they can change analysis results without any migration file changing.

    Args:
        db_vendor: The active database vendor.
        rule_ids: The rule IDs that are active for this run (already reflects
            DISABLED_RULES, db-vendor gating and Django-version gating).
        check_reverse: Whether reverse-safety analysis is enabled (it adds
            ``RV0xx`` issues, so on/off must produce different fingerprints).

    Returns:
        A hex digest uniquely identifying this analysis configuration.
    """
    import django
    from django.conf import settings

    from django_safe_migrations import __version__
    from django_safe_migrations.conf import get_config

    try:
        config_blob = json.dumps(get_config(), sort_keys=True, default=repr)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        config_blob = repr(get_config())

    parts = {
        "cache_version": CACHE_VERSION,
        "package": __version__,
        "django": django.get_version(),
        "vendor": db_vendor,
        "use_tz": bool(getattr(settings, "USE_TZ", False)),
        "rules": sorted(rule_ids),
        "check_reverse": bool(check_reverse),
        "config": hashlib.sha256(config_blob.encode("utf-8")).hexdigest(),
    }
    blob = json.dumps(parts, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AnalysisCache:
    """An on-disk cache of per-migration analysis results.

    Entries are keyed by ``"<app_label>:<migration_name>"`` and validated by a
    dependency-aware content hash. The whole file is namespaced by a
    *fingerprint*; a mismatch discards every entry on load.
    """

    def __init__(self, path: str, fingerprint: str):
        """Initialise the cache, loading any compatible entries from disk.

        Args:
            path: Path to the cache file.
            fingerprint: The current analysis fingerprint (see
                :func:`compute_fingerprint`).
        """
        self.path = Path(path)
        self.fingerprint = fingerprint
        self._entries: dict[str, dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring unreadable cache %s: %s", self.path, exc)
            return
        if (
            data.get("cache_version") != CACHE_VERSION
            or data.get("fingerprint") != self.fingerprint
        ):
            logger.debug("Cache fingerprint/version mismatch; starting fresh")
            return
        entries = data.get("entries")
        if isinstance(entries, dict):
            self._entries = entries

    def get(self, key: str, content_hash: str) -> Optional[list[Issue]]:
        """Return cached issues for *key* if the content hash matches.

        Args:
            key: The migration cache key.
            content_hash: The dependency-aware content hash for the migration.

        Returns:
            The reconstructed issue list on a hit, else ``None``.
        """
        from django_safe_migrations.rules.base import Issue

        entry = self._entries.get(key)
        if entry is None or entry.get("hash") != content_hash:
            self._misses += 1
            return None
        self._hits += 1
        return [Issue.from_dict(d) for d in entry.get("issues", [])]

    def set(self, key: str, content_hash: str, issues: list[Issue]) -> None:
        """Store *issues* for *key* under *content_hash*."""
        self._entries[key] = {
            "hash": content_hash,
            "issues": [issue.to_dict() for issue in issues],
        }

    def save(self) -> None:
        """Write the cache to disk (best-effort)."""
        data = {
            "cache_version": CACHE_VERSION,
            "fingerprint": self.fingerprint,
            "entries": self._entries,
        }
        try:
            self.path.write_text(
                json.dumps(data, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("Could not write cache %s: %s", self.path, exc)

    @property
    def hits(self) -> int:
        """Number of cache hits this run."""
        return self._hits

    @property
    def misses(self) -> int:
        """Number of cache misses this run."""
        return self._misses
