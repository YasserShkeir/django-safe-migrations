"""Tests for the standalone CLI (django_safe_migrations.cli)."""

from __future__ import annotations

import json
import os

from django_safe_migrations import cli


def _raise(*args, **kwargs):
    raise ImportError("boom: cannot import settings")


class TestSetupDjango:
    """Tests for setup_django() error handling."""

    def test_surfaces_real_error_when_module_set(self, monkeypatch, capsys):
        """An explicit DJANGO_SETTINGS_MODULE that fails reports the real error.

        Previously the exception was swallowed and the CLI printed a misleading
        "please set DJANGO_SETTINGS_MODULE" even though it was set.
        """
        monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "broken.settings")
        import django

        monkeypatch.setattr(django, "setup", _raise)

        assert cli.setup_django() is False

        err = capsys.readouterr().err
        assert "broken.settings" in err
        assert "ImportError" in err
        assert "boom" in err

    def test_cleans_up_env_when_module_not_set(self, monkeypatch):
        """The probe env var is cleaned up when no module works.

        When no module is set and no candidate succeeds, ``setup_django``
        returns False and removes the temporary ``DJANGO_SETTINGS_MODULE``.
        """
        monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
        import django

        monkeypatch.setattr(django, "setup", _raise)

        assert cli.setup_django() is False
        assert "DJANGO_SETTINGS_MODULE" not in os.environ


class TestMain:
    """Tests for the main() entry point."""

    def test_list_rules_returns_zero(self, capsys):
        """--list-rules works without Django setup and lists rule IDs."""
        rc = cli.main(["--list-rules"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "SM001" in out

    def test_list_rules_json_is_valid(self, capsys):
        """--list-rules --format=json emits parseable JSON of all rules."""
        rc = cli.main(["--list-rules", "--format=json"])
        out = capsys.readouterr().out

        assert rc == 0
        data = json.loads(out)
        assert any(rule["rule_id"] == "SM001" for rule in data)

    def test_no_misleading_hint_when_module_is_set(self, monkeypatch, capsys):
        """No misleading hint is shown when the module is set.

        When ``DJANGO_SETTINGS_MODULE`` is set but setup fails, ``main()``
        exits 1 without printing the "please set it" hint.
        """
        monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "broken.settings")
        monkeypatch.setattr(cli, "setup_django", lambda: False)

        rc = cli.main(["myapp"])
        err = capsys.readouterr().err

        assert rc == 1
        assert "Please set" not in err

    def test_hint_shown_when_module_not_set(self, monkeypatch, capsys):
        """The hint is shown when the module is not set.

        When ``DJANGO_SETTINGS_MODULE`` is unset and setup fails, ``main()``
        prints the helpful hint.
        """
        monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
        monkeypatch.setattr(cli, "setup_django", lambda: False)

        rc = cli.main(["myapp"])
        err = capsys.readouterr().err

        assert rc == 1
        assert "DJANGO_SETTINGS_MODULE" in err

    def test_diff_and_since_commit_mutually_exclusive(self, monkeypatch, capsys):
        """Passing both --diff and --since-commit returns exit code 2."""
        monkeypatch.setattr(cli, "setup_django", lambda: True)

        rc = cli.main(["--diff", "main", "--since-commit", "abc123"])
        err = capsys.readouterr().err

        assert rc == 2
        assert "only one of" in err.lower()

    def test_since_commit_uses_committed_range(self, monkeypatch, capsys):
        """--since-commit routes through get_committed_apps_and_migrations."""
        monkeypatch.setattr(cli, "setup_django", lambda: True)

        from django_safe_migrations import diff as diff_mod

        called = {}

        def fake_committed(commit):
            called["commit"] = commit
            return []

        monkeypatch.setattr(
            diff_mod, "get_committed_apps_and_migrations", fake_committed
        )

        rc = cli.main(["--since-commit", "abc123", "--format=json"])
        out = capsys.readouterr().out

        assert rc == 0
        assert called["commit"] == "abc123"
        # No changed migrations -> empty issue set.
        assert json.loads(out)["total"] == 0
