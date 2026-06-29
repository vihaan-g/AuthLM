from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from authlm.cli import _context, cli
from authlm.credentials import ApiKeyCredential
from authlm.metadata import MetadataEntry, MetadataStore
from authlm.stores import MemoryStore


def _patch_store(monkeypatch: pytest.MonkeyPatch, store: MemoryStore) -> None:
    monkeypatch.setattr(_context, "get_store", lambda *, store_name: store)


def test_disconnect_confirmed(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="x"
        )
    )
    _patch_store(monkeypatch, store)
    meta = MetadataStore(path=tmp_path / "m.json")
    meta.set(
        "openai",
        "default",
        MetadataEntry(
            provider_display_name="OpenAI",
            method_id="api_key",
            connected_at=datetime(2026, 6, 29, tzinfo=UTC),
        ),
    )
    result = runner.invoke(
        cli,
        [
            "disconnect",
            "openai",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert store.get("openai", "default") is None
    assert meta.get("openai", "default") is None


def test_disconnect_declined(
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
            "disconnect",
            "openai",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="n\n",
    )
    assert result.exit_code == 0, result.output
    assert store.get("openai", "default") is not None


def test_disconnect_yes_flag(
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
            "disconnect",
            "openai",
            "--yes",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert store.get("openai", "default") is None


def test_disconnect_missing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_store(monkeypatch, MemoryStore())
    result = runner.invoke(
        cli,
        [
            "disconnect",
            "openai",
            "--yes",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
