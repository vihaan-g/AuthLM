from __future__ import annotations

from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.stores.base import CredentialStore
from authlm.stores.memory_store import MemoryStore


def _api_key() -> ApiKeyCredential:
    return ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )


def _oauth() -> OAuthCredential:
    return OAuthCredential(
        provider="openai",
        alias="work",
        method_id="m",
        access_token="a",
        refresh_token="r",
        expires_at=None,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(MemoryStore(), CredentialStore)


def test_set_and_get_api_key() -> None:
    store = MemoryStore()
    store.set(_api_key())
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_set_and_get_oauth() -> None:
    store = MemoryStore()
    store.set(_oauth())
    cred = store.get("openai", "work")
    assert cred is not None
    assert isinstance(cred, OAuthCredential)
    assert cred.access_token == "a"


def test_get_missing_returns_none() -> None:
    assert MemoryStore().get("openai", "default") is None


def test_set_overwrites() -> None:
    store = MemoryStore()
    store.set(_api_key())
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-new"
        )
    )
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-new"


def test_delete_existing_returns_true() -> None:
    store = MemoryStore()
    store.set(_api_key())
    assert store.delete("openai", "default") is True
    assert store.get("openai", "default") is None


def test_delete_missing_returns_false() -> None:
    assert MemoryStore().delete("openai", "default") is False


def test_list() -> None:
    store = MemoryStore()
    store.set(_api_key())
    store.set(_oauth())
    pairs = sorted(store.list())
    assert pairs == [("openai", "default"), ("openai", "work")]


def test_backend_name() -> None:
    assert MemoryStore().backend_name() == "Memory"
