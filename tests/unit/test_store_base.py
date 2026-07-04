from __future__ import annotations

from authlm.stores.base import CredentialStore
from authlm.stores.memory_store import MemoryStore


def test_memory_store_satisfies_protocol() -> None:
    """MemoryStore satisfies the CredentialStore Protocol."""
    store = MemoryStore()
    assert isinstance(store, CredentialStore)


def test_protocol_has_five_methods() -> None:
    """CredentialStore Protocol requires get, set, delete, list, backend_name."""
    store = MemoryStore()
    assert hasattr(store, "get")
    assert hasattr(store, "set")
    assert hasattr(store, "delete")
    assert hasattr(store, "list")
    assert hasattr(store, "backend_name")
