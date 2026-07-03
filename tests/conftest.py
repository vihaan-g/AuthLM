from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from authlm.credentials import Credential, parse_credential
from authlm.stores.base import CredentialStore


@pytest.fixture
def runner() -> CliRunner:
    """A Click CliRunner for CLI tests."""
    return CliRunner()


@pytest.fixture(autouse=True, scope="session")
def _mark_called_from_test() -> None:
    """Set sentinel so authlm skips third-party plugin autoload in tests."""
    sys._called_from_test = True  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect authlm user path to a tmp dir and force the null keyring backend."""
    monkeypatch.setenv("AUTHLM_USER_PATH", str(tmp_path / "authlm"))
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")


class _StubStore(CredentialStore):
    """In-memory stub for connection method tests."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], str] = {}

    def get(self, provider: str, alias: str) -> Credential | None:
        key = (provider, alias)
        if key not in self._entries:
            return None
        return parse_credential(self._entries[key])

    def set(self, credential: Credential) -> None:
        self._entries[(credential.provider, credential.alias)] = (
            credential.model_dump_json()
        )

    def delete(self, provider: str, alias: str) -> bool:
        key = (provider, alias)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def list(self) -> Iterator[tuple[str, str]]:
        yield from self._entries

    def backend_name(self) -> str:
        return "stub"


@pytest.fixture
def stub_store() -> _StubStore:
    return _StubStore()
