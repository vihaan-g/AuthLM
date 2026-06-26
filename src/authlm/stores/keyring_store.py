from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import keyring
from keyring import errors
from typing_extensions import override

from authlm.credentials import Credential, parse_credential
from authlm.errors import SecretStoreError
from authlm.stores.base import CredentialStore

_Index = list[list[str]]


class KeyringStore(CredentialStore):
    """OS keychain-backed credential store via the keyring library."""

    def __init__(self, *, index_path: Path) -> None:
        self._index_path = index_path

    @override
    def get(self, provider: str, alias: str) -> Credential | None:
        try:
            raw = keyring.get_password(self._service(provider), alias)
        except Exception as exc:
            raise SecretStoreError(str(exc)) from exc
        if raw is None:
            return None
        return parse_credential(raw)

    @override
    def set(self, credential: Credential) -> None:
        try:
            keyring.set_password(
                self._service(credential.provider),
                credential.alias,
                credential.model_dump_json(),
            )
        except Exception as exc:
            raise SecretStoreError(str(exc)) from exc
        try:
            self._index_add(credential.provider, credential.alias)
        except OSError as exc:
            raise SecretStoreError(str(exc)) from exc

    @override
    def delete(self, provider: str, alias: str) -> bool:
        try:
            keyring.delete_password(self._service(provider), alias)
        except errors.PasswordDeleteError:
            return False
        except Exception as exc:
            raise SecretStoreError(str(exc)) from exc
        try:
            self._index_remove(provider, alias)
        except OSError as exc:
            raise SecretStoreError(str(exc)) from exc
        return True

    @override
    def list(self) -> Iterator[tuple[str, str]]:
        for pair in self._index_read():
            yield (pair[0], pair[1])

    @override
    def backend_name(self) -> str:
        return keyring.get_keyring().name

    @staticmethod
    def _service(provider: str) -> str:
        return f"authlm:{provider}"

    def _index_read(self) -> _Index:
        if not self._index_path.exists():
            return []
        try:
            data: _Index = json.loads(self._index_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SecretStoreError(str(exc)) from exc
        return data

    def _index_write(self, entries: _Index) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._index_path.write_text(json.dumps(entries))
        except OSError as exc:
            raise SecretStoreError(str(exc)) from exc

    def _index_add(self, provider: str, alias: str) -> None:
        entries = self._index_read()
        pair = [provider, alias]
        if pair not in entries:
            entries.append(pair)
        self._index_write(entries)

    def _index_remove(self, provider: str, alias: str) -> None:
        entries = self._index_read()
        entries = [e for e in entries if e != [provider, alias]]
        self._index_write(entries)
