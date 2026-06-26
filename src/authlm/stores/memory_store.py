from __future__ import annotations

from collections.abc import Iterator

from typing_extensions import override

from authlm.credentials import Credential, parse_credential
from authlm.stores.base import CredentialStore


class MemoryStore(CredentialStore):
    """In-process credential store. Cleared on process exit."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], str] = {}

    @override
    def get(self, provider: str, alias: str) -> Credential | None:
        raw = self._entries.get((provider, alias))
        if raw is None:
            return None
        return parse_credential(raw)

    @override
    def set(self, credential: Credential) -> None:
        self._entries[(credential.provider, credential.alias)] = (
            credential.model_dump_json()
        )

    @override
    def delete(self, provider: str, alias: str) -> bool:
        key = (provider, alias)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    @override
    def list(self) -> Iterator[tuple[str, str]]:
        yield from self._entries

    @override
    def backend_name(self) -> str:
        return "Memory"
