from __future__ import annotations

import sys

import pytest

from authlm.cli._context import get_store, is_tty
from authlm.stores import (
    EnvStore,
    KeyringStore,
    MemoryStore,
)


def test_get_store_memory() -> None:
    assert isinstance(get_store(store_name="memory"), MemoryStore)


def test_get_store_env() -> None:
    assert isinstance(get_store(store_name="env"), EnvStore)


def test_get_store_keyring() -> None:
    assert isinstance(get_store(store_name="keyring"), KeyringStore)


def test_is_tty_reflects_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert is_tty() is True
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert is_tty() is False
