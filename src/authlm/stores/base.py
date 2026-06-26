from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from authlm.credentials import Credential


@runtime_checkable
class CredentialStore(Protocol):
    """Pluggable persistence for credentials.

    Default implementation uses the OS keychain via ``keyring``.
    """

    def get(self, provider: str, alias: str) -> Credential | None:
        """Retrieve a credential, or None if not found."""
        ...

    def set(self, credential: Credential) -> None:
        """Persist a credential, overwriting any existing (provider, alias)."""
        ...

    def delete(self, provider: str, alias: str) -> bool:
        """Delete a credential; return True if it existed."""
        ...

    def list(self) -> Iterator[tuple[str, str]]:
        """Yield (provider, alias) pairs for all stored credentials."""
        ...

    def backend_name(self) -> str:
        """Human-readable name of the active backend."""
        ...
