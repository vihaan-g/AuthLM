from __future__ import annotations

from datetime import UTC, datetime

from authlm.cli._formatters import format_list_table, format_status_table
from authlm.credentials import ApiKeyCredential
from authlm.metadata import MetadataEntry


def _metadata(*, last_validated_at: datetime | None = None) -> MetadataEntry:
    return MetadataEntry(
        provider_display_name="OpenAI",
        method_id="api_key",
        connected_at=datetime(2026, 6, 29, tzinfo=UTC),
        last_validated_at=last_validated_at,
    )


def test_format_list_table_empty() -> None:
    out = format_list_table([], backend_name="Memory")
    assert out == "No credentials stored.\n"


def test_format_list_table_single_entry() -> None:
    out = format_list_table([("openai", "default")], backend_name="Memory")
    assert "PROVIDER" in out
    assert "ALIAS" in out
    assert "openai" in out
    assert "default" in out
    assert "Memory" in out
    assert out.endswith("\n")


def test_format_list_table_multiple_entries() -> None:
    out = format_list_table(
        [("openai", "personal"), ("openai", "work")], backend_name="Memory"
    )
    assert "personal" in out
    assert "work" in out


def test_format_status_table_contains_metadata() -> None:
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="redacted"
    )
    out = format_status_table(cred, _metadata(), backend_name="Memory")
    assert "Provider: openai" in out
    assert "Alias: default" in out
    assert "Method: api_key" in out
    assert "Backend: Memory" in out
