from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from authlm.cli import _context, cli
from authlm.credentials import ApiKeyCredential
from authlm.stores import MemoryStore


def _patch_store(monkeypatch: pytest.MonkeyPatch, store: MemoryStore) -> None:
    monkeypatch.setattr(_context, "get_store", lambda *, store_name: store)


def test_status_no_args_lists_all_providers(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    store.set(
        ApiKeyCredential(
            provider="anthropic", alias="default", method_id="api_key", secret="y"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        ["status", "--store", "memory", "--metadata-path", str(tmp_path / "m.json")],
    )
    assert result.exit_code == 0, result.output
    assert "openai" in result.output
    assert "anthropic" in result.output


def test_status_specific_provider(
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
        [
            "status",
            "openai",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "openai" in result.output
    assert "Provider: openai" in result.output


def test_status_specific_alias_not_found(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        [
            "status",
            "openai",
            "--alias",
            "work",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "work" in result.output


def test_status_all_aliases(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="personal", method_id="api_key", secret="x"
        )
    )
    store.set(
        ApiKeyCredential(
            provider="openai", alias="work", method_id="api_key", secret="y"
        )
    )
    _patch_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        [
            "status",
            "openai",
            "--all",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "personal" in result.output
    assert "work" in result.output


def test_status_with_validate(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    _patch_store(monkeypatch, store)
    with patch("authlm.cli.status._validate", new=AsyncMock(return_value=True)):
        result = runner.invoke(
            cli,
            [
                "status",
                "openai",
                "--validate",
                "--store",
                "memory",
                "--metadata-path",
                str(tmp_path / "m.json"),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "Valid" in result.output


def test_status_validate_force_warns_on_warned_method(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §7: --force on a warned method prints a 'may be detectable' warning."""
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="anthropic",
            alias="default",
            method_id="claude_pro_oauth_browser",
            secret="x",
        )
    )
    _patch_store(monkeypatch, store)
    with patch("authlm.cli.status._validate", new=AsyncMock(return_value=True)):
        result = runner.invoke(
            cli,
            [
                "status",
                "anthropic",
                "--validate",
                "--force",
                "--store",
                "memory",
                "--metadata-path",
                str(tmp_path / "m.json"),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "detectable" in result.output


def test_status_validate_warned_without_force_returns_permission_error(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §7: validate() refuses warned methods unless force=True;
    the CLI must surface the error cleanly (not a Python traceback)."""
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="anthropic",
            alias="default",
            method_id="claude_pro_oauth_browser",
            secret="x",
        )
    )
    _patch_store(monkeypatch, store)
    with patch(
        "authlm.cli.status._validate",
        new=AsyncMock(side_effect=PermissionError("warned method")),
    ):
        result = runner.invoke(
            cli,
            [
                "status",
                "anthropic",
                "--validate",
                "--store",
                "memory",
                "--metadata-path",
                str(tmp_path / "m.json"),
            ],
        )
    assert result.exit_code != 0
    assert "traceback" not in result.output.lower()
    assert "warned" in result.output.lower()
