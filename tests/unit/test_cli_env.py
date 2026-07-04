from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from authlm.cli import _context, cli
from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.stores import MemoryStore


def _patch_store(monkeypatch: pytest.MonkeyPatch, store: MemoryStore) -> None:
    monkeypatch.setattr(_context, "get_store", lambda *, store_name: store)


def test_env_api_key(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-test"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_API_KEY=sk-test" in result.output


def test_env_shell_format_explicit(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--export-format", "shell", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_API_KEY=x" in result.output


def test_env_docker_format(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--export-format", "docker", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_API_KEY=x" in result.output


def test_env_github_format(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--export-format", "github", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in result.output


def test_env_oauth(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        OAuthCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            access_token="ACCESS",
            refresh_token="REFRESH",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_ACCESS_TOKEN=ACCESS" in result.output
    assert "OPENAI_REFRESH_TOKEN" not in result.output


def test_env_oauth_with_include_refresh_token(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        OAuthCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            access_token="ACCESS",
            refresh_token="REFRESH",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--store", "memory", "--include-refresh-token"],
    )
    assert result.exit_code == 0, result.output
    assert "OPENAI_ACCESS_TOKEN=ACCESS" in result.output
    assert "OPENAI_REFRESH_TOKEN=REFRESH" in result.output


def test_env_missing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_store(monkeypatch, MemoryStore())
    result = runner.invoke(cli, ["env", "openai", "--store", "memory"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "openai" in result.output


def test_docker_format_has_no_shell_quoting(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Docker format outputs bare KEY=VALUE without shlex.quote."""
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai",
            alias="default",
            method_id="api_key",
            secret="sk test value",
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["env", "openai", "--export-format", "docker", "--store", "memory"],
    )
    assert result.exit_code == 0, result.output
    assert "'" not in result.output
    assert "OPENAI_API_KEY=sk test value" in result.output
