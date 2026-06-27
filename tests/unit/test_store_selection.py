from __future__ import annotations

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.backends import null as _null
from typing_extensions import override

from authlm.errors import AuthLMError
from authlm.stores import (
    EncryptedFileStore,
    EnvStore,
    KeyringStore,
    MemoryStore,
    get_default_store,
)


class _RealKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()

    @override
    def get_password(self, service: str, username: str) -> str | None:
        return None

    @override
    def set_password(self, service: str, username: str, password: str) -> None:
        pass

    @override
    def delete_password(self, service: str, username: str) -> None:
        pass


def test_authlm_store_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "memory")
    store = get_default_store()
    assert isinstance(store, MemoryStore)


def test_authlm_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "env")
    store = get_default_store()
    assert isinstance(store, EnvStore)


def test_authlm_store_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "keyring")
    store = get_default_store()
    assert isinstance(store, KeyringStore)


def test_authlm_store_encrypted_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "encrypted_file")
    monkeypatch.setenv("AUTHLM_PASSPHRASE", "test-pass")
    store = get_default_store()
    assert isinstance(store, EncryptedFileStore)


def test_encrypted_file_warns_on_env_passphrase(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "encrypted_file")
    monkeypatch.setenv("AUTHLM_PASSPHRASE", "test-pass")
    with caplog.at_level("WARNING", logger="authlm.stores"):
        get_default_store()
    assert any(
        "AUTHLM_PASSPHRASE" in record.message and record.levelname == "WARNING"
        for record in caplog.records
    )


def test_authlm_store_encrypted_file_without_passphrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "encrypted_file")
    monkeypatch.delenv("AUTHLM_PASSPHRASE", raising=False)
    with pytest.raises(AuthLMError):
        get_default_store()


def test_authlm_store_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_STORE", "unknown")
    with pytest.raises(AuthLMError):
        get_default_store()


def test_auto_select_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHLM_STORE", raising=False)
    original = keyring.get_keyring()
    keyring.set_keyring(_RealKeyring())
    try:
        store = get_default_store()
        assert isinstance(store, KeyringStore)
    finally:
        keyring.set_keyring(original)


def test_auto_select_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHLM_STORE", raising=False)
    original = keyring.get_keyring()
    keyring.set_keyring(_null.Keyring())
    try:
        store = get_default_store()
        assert isinstance(store, EnvStore)
    finally:
        keyring.set_keyring(original)
