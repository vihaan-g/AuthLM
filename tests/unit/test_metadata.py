from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from authlm.metadata import MetadataEntry, MetadataStore


def _entry() -> MetadataEntry:
    return MetadataEntry(
        provider_display_name="OpenAI",
        method_id="api_key",
        connected_at=datetime(2026, 6, 26, tzinfo=UTC),
    )


def test_set_and_get(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    store.set("openai", "default", _entry())
    entry = store.get("openai", "default")
    assert entry is not None
    assert entry.provider_display_name == "OpenAI"
    assert entry.method_id == "api_key"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    assert store.get("openai", "default") is None


def test_delete_existing_returns_true(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    store.set("openai", "default", _entry())
    assert store.delete("openai", "default") is True
    assert store.get("openai", "default") is None


def test_delete_missing_returns_false(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    assert store.delete("openai", "default") is False


def test_list(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    store.set("openai", "default", _entry())
    store.set("anthropic", "work", _entry())
    pairs = sorted(store.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_persists_to_file(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    store1 = MetadataStore(path=path)
    store1.set("openai", "default", _entry())
    store2 = MetadataStore(path=path)
    entry = store2.get("openai", "default")
    assert entry is not None
    assert entry.provider_display_name == "OpenAI"


def test_set_overwrites(tmp_path: Path) -> None:
    store = MetadataStore(path=tmp_path / "metadata.json")
    store.set("openai", "default", _entry())
    updated = MetadataEntry(
        provider_display_name="OpenAI",
        method_id="api_key",
        connected_at=datetime(2026, 6, 26, tzinfo=UTC),
        last_validated_at=datetime(2026, 6, 27, tzinfo=UTC),
    )
    store.set("openai", "default", updated)
    entry = store.get("openai", "default")
    assert entry is not None
    assert entry.last_validated_at is not None


def test_optional_fields_default() -> None:
    entry = MetadataEntry(
        provider_display_name="Test",
        method_id="api_key",
        connected_at=datetime(2026, 6, 26, tzinfo=UTC),
    )
    assert entry.last_validated_at is None
    assert entry.warning_acknowledged_at is None
    assert entry.scopes == []


def test_metadata_entry_has_fingerprint_field() -> None:
    from datetime import UTC, datetime

    entry = MetadataEntry(
        provider_display_name="OpenAI",
        method_id="api_key",
        connected_at=datetime.now(UTC),
        fingerprint="abc123",
    )
    assert entry.fingerprint == "abc123"


def test_metadata_entry_has_client_id_field() -> None:
    from datetime import UTC, datetime

    entry = MetadataEntry(
        provider_display_name="OpenAI",
        method_id="oauth_browser",
        connected_at=datetime.now(UTC),
        client_id="app_test123",
    )
    assert entry.client_id == "app_test123"
