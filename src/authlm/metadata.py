from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class MetadataEntry(BaseModel):
    provider_display_name: str
    method_id: str
    connected_at: datetime
    last_validated_at: datetime | None = None
    warning_acknowledged_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    client_id: str | None = None
    fingerprint: str | None = None


class MetadataStore:
    """Read/write non-secret credential metadata to a JSON file."""

    def __init__(self, *, path: Path) -> None:
        self._path = path

    def get(self, provider: str, alias: str) -> MetadataEntry | None:
        data = self._read()
        entry = data.get(provider, {}).get(alias)
        if entry is None:
            return None
        return MetadataEntry.model_validate(entry)

    def set(self, provider: str, alias: str, entry: MetadataEntry) -> None:
        data = self._read()
        data.setdefault(provider, {})[alias] = entry.model_dump(mode="json")
        self._write(data)

    def delete(self, provider: str, alias: str) -> bool:
        data = self._read()
        provider_entries = data.get(provider)
        if provider_entries is None or alias not in provider_entries:
            return False
        del provider_entries[alias]
        if not provider_entries:
            del data[provider]
        self._write(data)
        return True

    def list(self) -> Iterator[tuple[str, str]]:
        data = self._read()
        for provider, aliases in data.items():
            for alias in aliases:
                yield (provider, alias)

    def _read(self) -> dict[str, dict[str, dict[str, object]]]:
        if not self._path.exists():
            return {}
        loaded: dict[str, dict[str, dict[str, object]]] = json.loads(
            self._path.read_text()
        )
        return loaded

    def _write(self, data: dict[str, dict[str, dict[str, object]]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        os.replace(tmp_path, self._path)
