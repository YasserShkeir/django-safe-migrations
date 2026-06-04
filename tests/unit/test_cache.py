"""Tests for lint result caching (django_safe_migrations.cache)."""

from __future__ import annotations

import json

from django_safe_migrations.analyzer import MigrationAnalyzer
from django_safe_migrations.cache import (
    CACHE_VERSION,
    AnalysisCache,
    compute_fingerprint,
    file_sha256,
)
from django_safe_migrations.rules.base import Issue, Severity


def _issue(rule_id="SM001", **kw):
    defaults = dict(
        rule_id=rule_id,
        severity=Severity.WARNING,
        operation="AddField",
        message="msg",
        suggestion="fix it",
        file_path="/x/migrations/0001_initial.py",
        line_number=7,
        app_label="testapp",
        migration_name="0001_initial",
        operation_index=0,
    )
    defaults.update(kw)
    return Issue(**defaults)


class TestFileSha256:
    """Tests for file_sha256."""

    def test_hashes_file_bytes(self, tmp_path):
        """The digest matches hashlib over the same bytes."""
        import hashlib

        p = tmp_path / "m.py"
        p.write_bytes(b"some migration content")
        assert (
            file_sha256(str(p)) == hashlib.sha256(b"some migration content").hexdigest()
        )

    def test_changes_with_content(self, tmp_path):
        """Different content yields a different digest."""
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("aaa")
        b.write_text("bbb")
        assert file_sha256(str(a)) != file_sha256(str(b))


class TestFingerprint:
    """Tests for compute_fingerprint."""

    def test_stable_for_same_inputs(self):
        """Identical inputs produce identical fingerprints."""
        fp1 = compute_fingerprint("postgresql", ["SM001", "SM002"])
        fp2 = compute_fingerprint("postgresql", ["SM002", "SM001"])  # order-independent
        assert fp1 == fp2

    def test_differs_by_vendor(self):
        """Changing the vendor changes the fingerprint."""
        assert compute_fingerprint("postgresql", ["SM001"]) != compute_fingerprint(
            "mysql", ["SM001"]
        )

    def test_differs_by_ruleset(self):
        """Changing the active rule set changes the fingerprint."""
        assert compute_fingerprint("postgresql", ["SM001"]) != compute_fingerprint(
            "postgresql", ["SM001", "SM002"]
        )


class TestIssueRoundTrip:
    """Issue.to_dict / from_dict round-trips for the cache."""

    def test_round_trip_preserves_all_fields(self):
        """from_dict(to_dict(issue)) reproduces every field, severity enum included."""
        issue = _issue()
        restored = Issue.from_dict(issue.to_dict())
        assert restored == issue
        assert restored.severity is Severity.WARNING

    def test_round_trip_with_nones(self):
        """Optional fields left as None survive the round-trip."""
        issue = _issue(suggestion=None, line_number=None, operation_index=None)
        assert Issue.from_dict(issue.to_dict()) == issue


class TestAnalysisCache:
    """Tests for the AnalysisCache store."""

    def test_set_get_round_trip(self, tmp_path):
        """A stored entry is returned for a matching content hash."""
        cache = AnalysisCache(str(tmp_path / "c.json"), "fp")
        cache.set("testapp:0001_initial", "hash1", [_issue()])

        got = cache.get("testapp:0001_initial", "hash1")
        assert got == [_issue()]
        assert cache.hits == 1
        assert cache.misses == 0

    def test_miss_on_hash_mismatch(self, tmp_path):
        """A changed content hash is a miss (the migration must be re-analysed)."""
        cache = AnalysisCache(str(tmp_path / "c.json"), "fp")
        cache.set("testapp:0001_initial", "hash1", [_issue()])

        assert cache.get("testapp:0001_initial", "hash2") is None
        assert cache.misses == 1

    def test_miss_on_unknown_key(self, tmp_path):
        """An unknown key is a miss."""
        cache = AnalysisCache(str(tmp_path / "c.json"), "fp")
        assert cache.get("nope:0001", "h") is None

    def test_save_and_reload(self, tmp_path):
        """Entries persist across instances sharing the same file + fingerprint."""
        path = str(tmp_path / "c.json")
        cache = AnalysisCache(path, "fp")
        cache.set("testapp:0001_initial", "hash1", [_issue()])
        cache.save()

        reloaded = AnalysisCache(path, "fp")
        assert reloaded.get("testapp:0001_initial", "hash1") == [_issue()]

    def test_fingerprint_mismatch_discards(self, tmp_path):
        """A different fingerprint discards all entries on load."""
        path = str(tmp_path / "c.json")
        cache = AnalysisCache(path, "fp-old")
        cache.set("testapp:0001_initial", "hash1", [_issue()])
        cache.save()

        reloaded = AnalysisCache(path, "fp-new")
        assert reloaded.get("testapp:0001_initial", "hash1") is None

    def test_corrupt_cache_is_ignored(self, tmp_path):
        """An unreadable / corrupt cache file is ignored, not fatal."""
        path = tmp_path / "c.json"
        path.write_text("{ this is not json")
        cache = AnalysisCache(str(path), "fp")
        assert cache.get("any", "h") is None  # starts empty

    def test_saved_file_records_version_and_fingerprint(self, tmp_path):
        """The persisted file records cache_version and fingerprint."""
        path = tmp_path / "c.json"
        cache = AnalysisCache(str(path), "fp123")
        cache.set("k", "h", [_issue()])
        cache.save()

        data = json.loads(path.read_text())
        assert data["cache_version"] == CACHE_VERSION
        assert data["fingerprint"] == "fp123"
        assert "k" in data["entries"]


class TestAnalyzerCaching:
    """End-to-end: the analyzer serves unchanged migrations from the cache."""

    def _fingerprint(self, analyzer):
        return compute_fingerprint(
            analyzer.db_vendor, [r.rule_id for r in analyzer.rules]
        )

    def test_second_run_hits_and_matches(self, tmp_path):
        """A second run (fresh instance, same file) hits cache with identical issues."""
        path = str(tmp_path / "c.json")

        a1 = MigrationAnalyzer()
        a1.cache = AnalysisCache(path, self._fingerprint(a1))
        issues1 = a1.analyze_app("testapp")
        a1.cache.save()

        assert a1.cache.misses > 0
        assert a1.cache.hits == 0

        a2 = MigrationAnalyzer()
        a2.cache = AnalysisCache(path, self._fingerprint(a2))
        issues2 = a2.analyze_app("testapp")

        # Every migration served from cache, no fresh analysis.
        assert a2.cache.hits > 0
        assert a2.cache.misses == 0
        # Results are identical to the uncached run.
        assert [i.to_dict() for i in issues1] == [i.to_dict() for i in issues2]

    def test_cached_equals_uncached(self, tmp_path):
        """Cache-enabled output equals cache-disabled output (correctness)."""
        uncached = MigrationAnalyzer().analyze_app("testapp")

        a = MigrationAnalyzer()
        a.cache = AnalysisCache(str(tmp_path / "c.json"), self._fingerprint(a))
        cached = a.analyze_app("testapp")

        assert [i.to_dict() for i in uncached] == [i.to_dict() for i in cached]
