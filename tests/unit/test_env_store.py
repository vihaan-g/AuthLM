from __future__ import annotations

import pytest

from authlm.credentials import ApiKeyCredential
from authlm.errors import CredentialNotFound, SecretStoreError
from authlm.stores.base import CredentialStore
from authlm.stores.env_store import EnvStore


def _store() -> EnvStore:
    return EnvStore(
        mapping={"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    )


def test_satisfies_protocol() -> None:
    assert isinstance(_store(), CredentialStore)


def test_get_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    cred = _store().get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-from-env"
    assert cred.method_id == "env"


def test_get_missing_env_var_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _store().get("openai", "default") is None


def test_get_unknown_provider_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert _store().get("unknown", "default") is None


def test_get_non_default_alias_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(CredentialNotFound):
        _store().get("openai", "work")


def test_set_raises_secret_store_error() -> None:
    with pytest.raises(SecretStoreError, match="read-only"):
        _store().set(
            ApiKeyCredential(
                provider="openai", alias="default", method_id="env", secret="s"
            )
        )


def test_delete_raises_secret_store_error() -> None:
    with pytest.raises(SecretStoreError, match="read-only"):
        _store().delete("openai", "default")


def test_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pairs = list(_store().list())
    assert pairs == [("openai", "default")]


def test_backend_name() -> None:
    assert _store().backend_name() == "Environment"
