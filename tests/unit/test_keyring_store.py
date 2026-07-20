from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import keyring
import pytest
from keyring import errors
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError
from typing_extensions import override

from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.errors import SecretStoreError
from authlm.stores.base import CredentialStore
from authlm.stores.keyring_store import KeyringStore


class InMemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self._store: dict[tuple[str, str], str] = {}

    @override
    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    @override
    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    @override
    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            raise errors.PasswordDeleteError("not found")
        del self._store[(service, username)]


@pytest.fixture
def in_memory_keyring() -> Iterator[InMemoryKeyring]:
    original = keyring.get_keyring()
    backend = InMemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(original)


def _api_key() -> ApiKeyCredential:
    return ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )


def _oauth() -> OAuthCredential:
    return OAuthCredential(
        provider="anthropic",
        alias="work",
        method_id="m",
        access_token="a",
        refresh_token="r",
        expires_at=None,
    )


def test_satisfies_protocol(tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    assert isinstance(store, CredentialStore)


def test_set_and_get(in_memory_keyring: InMemoryKeyring, tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    store.set(_api_key())
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_get_missing_returns_none(
    in_memory_keyring: InMemoryKeyring, tmp_path: Path
) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    assert store.get("openai", "default") is None


def test_delete_existing(in_memory_keyring: InMemoryKeyring, tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    store.set(_api_key())
    assert store.delete("openai", "default") is True
    assert store.get("openai", "default") is None


def test_delete_missing_returns_false(
    in_memory_keyring: InMemoryKeyring, tmp_path: Path
) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    assert store.delete("openai", "default") is False


def test_list(in_memory_keyring: InMemoryKeyring, tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    store.set(_api_key())
    store.set(_oauth())
    pairs = sorted(store.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_backend_name(in_memory_keyring: InMemoryKeyring, tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    name = store.backend_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_set_overwrites(in_memory_keyring: InMemoryKeyring, tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
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


def test_set_raises_secret_store_error_on_keyring_error(tmp_path: Path) -> None:
    store = KeyringStore(index_path=tmp_path / "index.json")
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    with (
        patch("keyring.set_password", side_effect=KeyringError("keyring locked")),
        pytest.raises(SecretStoreError, match="keyring locked"),
    ):
        store.set(cred)


def test_get_raises_secret_store_error_on_keyring_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get() wraps keyring errors in SecretStoreError."""
    store = KeyringStore(index_path=tmp_path / "index.json")

    def failing_get_password(service: str, username: str) -> None:
        raise keyring.errors.KeyringError("keychain is locked")

    monkeypatch.setattr(keyring, "get_password", failing_get_password)

    with pytest.raises(SecretStoreError, match="keychain is locked"):
        store.get("openai", "default")


def test_delete_raises_secret_store_error_on_keyring_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """delete() wraps non-PasswordDeleteError keyring errors in SecretStoreError."""
    store = KeyringStore(index_path=tmp_path / "index.json")
    store._index_write([["openai", "default"]])  # noqa: SLF001

    def failing_delete_password(service: str, username: str) -> None:
        raise keyring.errors.KeyringError("keychain unavailable")

    monkeypatch.setattr(keyring, "delete_password", failing_delete_password)

    with pytest.raises(SecretStoreError, match="keychain unavailable"):
        store.delete("openai", "default")


def test_list_raises_secret_store_error_on_corrupted_index(
    tmp_path: Path,
) -> None:
    """list() raises SecretStoreError when index file contains invalid JSON."""
    index_path = tmp_path / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("not valid json {{{")

    store = KeyringStore(index_path=index_path)

    with pytest.raises(SecretStoreError):
        list(store.list())


def test_get_raises_secret_store_error_on_generic_backend_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get() wraps non-KeyringError backend exceptions in SecretStoreError."""
    store = KeyringStore(index_path=tmp_path / "index.json")

    def failing_get_password(service: str, username: str) -> None:
        raise RuntimeError("SecretService D-Bus connection closed")

    monkeypatch.setattr(keyring, "get_password", failing_get_password)

    with pytest.raises(SecretStoreError, match="D-Bus connection closed"):
        store.get("openai", "default")


def test_set_raises_secret_store_error_on_generic_backend_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set() wraps non-KeyringError backend exceptions in SecretStoreError."""
    store = KeyringStore(index_path=tmp_path / "index.json")
    cred = _api_key()

    def failing_set_password(service: str, username: str, password: str) -> None:
        raise RuntimeError("SecretService D-Bus connection closed")

    monkeypatch.setattr(keyring, "set_password", failing_set_password)

    with pytest.raises(SecretStoreError, match="D-Bus connection closed"):
        store.set(cred)


def test_delete_raises_secret_store_error_on_generic_backend_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """delete() wraps non-KeyringError backend exceptions in SecretStoreError."""
    store = KeyringStore(index_path=tmp_path / "index.json")
    store._index_write([["openai", "default"]])  # noqa: SLF001

    def failing_delete_password(service: str, username: str) -> None:
        raise RuntimeError("SecretService D-Bus connection closed")

    monkeypatch.setattr(keyring, "delete_password", failing_delete_password)

    with pytest.raises(SecretStoreError, match="D-Bus connection closed"):
        store.delete("openai", "default")


def test_index_write_is_atomic(tmp_path: Path) -> None:
    """_index_write writes via .tmp and creates final index file."""
    index_path = tmp_path / "index.json"
    store = KeyringStore(index_path=index_path)
    store._index_write([["openai", "default"]])  # noqa: SLF001

    assert index_path.exists()
    assert not (tmp_path / "index.tmp").exists()
