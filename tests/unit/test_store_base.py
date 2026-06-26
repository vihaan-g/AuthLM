from __future__ import annotations

from collections.abc import Iterator

from authlm.credentials import Credential
from authlm.stores.base import CredentialStore


class _FakeStore:
    def get(self, provider: str, alias: str) -> Credential | None:
        return None

    def set(self, credential: Credential) -> None:
        pass

    def delete(self, provider: str, alias: str) -> bool:
        return False

    def list(self) -> Iterator[tuple[str, str]]:
        yield from ()

    def backend_name(self) -> str:
        return "fake"


def test_fake_store_satisfies_protocol() -> None:
    store: CredentialStore = _FakeStore()
    assert isinstance(store, CredentialStore)


def test_protocol_has_five_methods() -> None:
    for method_name in ("get", "set", "delete", "list", "backend_name"):
        assert hasattr(CredentialStore, method_name)
