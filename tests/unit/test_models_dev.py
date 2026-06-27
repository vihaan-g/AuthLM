from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from respx import MockRouter

from authlm.models_dev import (
    fetch_models_dev,
    get_provider_metadata,
    load_vendored_snapshot,
    refresh_cache,
)


def test_load_vendored_snapshot_has_four_providers() -> None:
    data = load_vendored_snapshot()
    assert "openai" in data
    assert "anthropic" in data
    assert "google" in data
    assert "openrouter" in data


def test_fetch_models_dev_parses(respx_mock: MockRouter) -> None:
    respx_mock.get("https://models.dev/api.json").respond(
        200, json={"openai": {"id": "openai", "name": "OpenAI", "models": {}}}
    )
    data = fetch_models_dev(http_client_factory=lambda: httpx.Client(timeout=5.0))
    assert "openai" in data
    assert data["openai"]["name"] == "OpenAI"


def test_fetch_models_dev_raises_on_5xx(respx_mock: MockRouter) -> None:
    respx_mock.get("https://models.dev/api.json").respond(503, text="upstream down")
    with pytest.raises(RuntimeError):
        fetch_models_dev(http_client_factory=lambda: httpx.Client(timeout=5.0))


def test_refresh_cache_writes_file(respx_mock: MockRouter, tmp_path: Path) -> None:
    respx_mock.get("https://models.dev/api.json").respond(
        200, json={"openai": {"id": "openai", "name": "OpenAI", "models": {}}}
    )
    path = tmp_path / "models-dev-cache.json"
    refresh_cache(
        cache_path=path, http_client_factory=lambda: httpx.Client(timeout=5.0)
    )
    assert path.exists()
    data = json.loads(path.read_text())
    assert "openai" in data


def test_get_provider_metadata_falls_back_to_vendored(
    respx_mock: MockRouter, tmp_path: Path
) -> None:
    respx_mock.get("https://models.dev/api.json").respond(500)
    metadata = get_provider_metadata(
        "openai",
        cache_path=tmp_path / "cache.json",
        http_client_factory=lambda: httpx.Client(timeout=5.0),
    )
    assert metadata is not None
    assert metadata["name"] == "OpenAI"
