from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from authlm.cli import cli
from authlm.cli import list_cmd as _list_mod
from authlm.credentials import ApiKeyCredential
from authlm.metadata import MetadataEntry, MetadataStore
from authlm.stores import MemoryStore


def test_list_empty(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        cli,
        ["list", "--store", "memory", "--metadata-path", str(tmp_path / "m.json")],
    )
    assert result.exit_code == 0
    assert "No credentials stored." in result.output


def test_list_single_entry(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="redacted"
        )
    )
    monkeypatch.setattr(_list_mod, "build_store", lambda *, store_name: store)
    result = runner.invoke(
        cli,
        ["list", "--store", "memory", "--metadata-path", str(tmp_path / "m.json")],
    )
    assert result.exit_code == 0
    assert "openai" in result.output
    assert "default" in result.output
    assert "api_key" in result.output
    assert "Memory" in result.output


def test_list_includes_metadata(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="redacted"
        )
    )
    monkeypatch.setattr(_list_mod, "build_store", lambda *, store_name: store)
    meta_path = tmp_path / "m.json"
    meta = MetadataStore(path=meta_path)
    meta.set(
        "openai",
        "default",
        MetadataEntry(
            provider_display_name="OpenAI",
            method_id="api_key",
            connected_at=datetime(2026, 6, 29, tzinfo=UTC),
            last_validated_at=datetime(2026, 6, 30, tzinfo=UTC),
        ),
    )
    result = runner.invoke(
        cli, ["list", "--store", "memory", "--metadata-path", str(meta_path)]
    )
    assert result.exit_code == 0
    assert "openai" in result.output
    assert "2026-06-30" in result.output


def test_list_multiple_entries(
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
    monkeypatch.setattr(_list_mod, "build_store", lambda *, store_name: store)
    result = runner.invoke(
        cli,
        ["list", "--store", "memory", "--metadata-path", str(tmp_path / "m.json")],
    )
    assert result.exit_code == 0
    assert "personal" in result.output
    assert "work" in result.output


def test_list_store_error_displays_clean_click_exception(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any

    from authlm.errors import SecretStoreError

    def _failing_store(*args: Any, **kwargs: Any) -> Any:
        class FailingStore:
            def list(self) -> Any:
                raise SecretStoreError("Keyring access locked")
            def backend_name(self) -> str:
                return "FailingStore"
        return FailingStore()

    monkeypatch.setattr(_list_mod, "build_store", _failing_store)
    result = runner.invoke(
        cli, ["list", "--store", "memory", "--metadata-path", str(tmp_path / "m.json")]
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Keyring access locked" in result.output
