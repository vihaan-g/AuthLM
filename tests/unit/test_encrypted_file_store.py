from __future__ import annotations

from pathlib import Path

import pytest

from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.errors import AuthLMError
from authlm.stores.base import CredentialStore
from authlm.stores.encrypted_file_store import EncryptedFileStore


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


def _store(tmp_path: Path, passphrase: str = "correct") -> EncryptedFileStore:
    return EncryptedFileStore(
        path=tmp_path / "creds.enc.json",
        passphrase=passphrase,
        iterations=1000,
    )


def test_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(_store(tmp_path), CredentialStore)


def test_set_and_get(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert _store(tmp_path).get("openai", "default") is None


def test_set_overwrites(tmp_path: Path) -> None:
    store = _store(tmp_path)
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


def test_delete_existing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    assert store.delete("openai", "default") is True
    assert store.get("openai", "default") is None


def test_delete_missing_returns_false(tmp_path: Path) -> None:
    assert _store(tmp_path).delete("openai", "default") is False


def test_list(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    store.set(_oauth())
    pairs = sorted(store.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_wrong_passphrase_raises(tmp_path: Path) -> None:
    store1 = _store(tmp_path, passphrase="correct")
    store1.set(_api_key())
    store2 = _store(tmp_path, passphrase="wrong")
    with pytest.raises(AuthLMError):
        store2.get("openai", "default")


def test_list_works_without_passphrase(tmp_path: Path) -> None:
    store1 = _store(tmp_path, passphrase="correct")
    store1.set(_api_key())
    store1.set(_oauth())
    store2 = _store(tmp_path, passphrase="wrong")
    pairs = sorted(store2.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_backend_name(tmp_path: Path) -> None:
    assert _store(tmp_path).backend_name() == "Encrypted File"


def test_persists_across_instances(tmp_path: Path) -> None:
    store1 = _store(tmp_path)
    store1.set(_api_key())
    store2 = _store(tmp_path)
    cred = store2.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_atomic_write_no_temp_file_left(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    path = tmp_path / "creds.enc.json"
    assert path.exists()
    assert not (tmp_path / "creds.enc.json.tmp").exists()


def test_file_permissions_owner_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    path = tmp_path / "creds.enc.json"
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
