from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from click.testing import CliRunner

from authlm.cli import cli
from authlm.credentials import ApiKeyCredential, compute_fingerprint
from authlm.metadata import MetadataEntry, MetadataStore
from authlm.stores import MemoryStore, set_store


def test_doctor_cmd_runs(runner: CliRunner, tmp_path: Path) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-test"
        )
    )
    meta_path = tmp_path / "metadata.json"
    set_store(store)
    try:
        result = runner.invoke(cli, ["doctor", "--metadata-path", str(meta_path)])
        assert result.exit_code == 0
        assert "AuthLM System & Storage Diagnostics" in result.output
        assert "Store Backend:" in result.output
    finally:
        set_store(None)


def test_doctor_cmd_with_mismatch(runner: CliRunner, tmp_path: Path) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai",
            alias="default",
            method_id="api_key",
            secret="sk-test-new",
        )
    )
    meta_path = tmp_path / "metadata.json"
    meta_store = MetadataStore(path=meta_path)
    old_fp = compute_fingerprint("sk-test-old")
    meta_store.set(
        "openai",
        "default",
        MetadataEntry(
            provider_display_name="OpenAI",
            method_id="api_key",
            connected_at=datetime.now(UTC),
            fingerprint=old_fp,
        ),
    )
    set_store(store)
    try:
        result = runner.invoke(cli, ["doctor", "--metadata-path", str(meta_path)])
        assert result.exit_code == 0
        assert "WARNING" in result.output
        assert "mismatch" in result.output
    finally:
        set_store(None)
