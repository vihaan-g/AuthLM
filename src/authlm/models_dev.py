from __future__ import annotations

import json
import logging
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

import httpx

_log = logging.getLogger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"


def load_vendored_snapshot() -> dict[str, Any]:
    raw = (
        resources.files("authlm._vendor")
        .joinpath("models-dev-snapshot.json")
        .read_text()
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Vendored models.dev snapshot is not a JSON object")
    return data


def fetch_models_dev(
    *,
    http_client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(
        timeout=30.0
    ),
) -> dict[str, Any]:
    with http_client_factory() as client:
        response = client.get(MODELS_DEV_URL)
    if not (200 <= response.status_code < 300):
        raise RuntimeError(
            f"models.dev fetch failed: status={response.status_code} "
            f"body={response.text[:200]}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("models.dev response was not a JSON object")
    return data


def refresh_cache(
    *,
    cache_path: Path,
    http_client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(
        timeout=30.0
    ),
) -> dict[str, Any]:
    data = fetch_models_dev(http_client_factory=http_client_factory)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2))
    return data


def get_provider_metadata(
    provider_id: str,
    *,
    cache_path: Path,
    http_client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(
        timeout=30.0
    ),
) -> dict[str, Any] | None:
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            _log.warning(
                "Failed to read models.dev cache at %s", cache_path, exc_info=True
            )
        else:
            if isinstance(cached, dict):
                value = cached.get(provider_id)
                if isinstance(value, dict):
                    return value
    try:
        return refresh_cache(
            cache_path=cache_path,
            http_client_factory=http_client_factory,
        ).get(provider_id)
    except Exception:
        _log.warning("Falling back to vendored models.dev snapshot", exc_info=True)
        return load_vendored_snapshot().get(provider_id)
