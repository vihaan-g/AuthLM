from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _mark_called_from_test() -> None:
    """Set sentinel so authlm skips third-party plugin autoload in tests."""
    sys._called_from_test = True  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect authlm user path to a tmp dir and force the null keyring backend."""
    monkeypatch.setenv("AUTHLM_USER_PATH", str(tmp_path / "authlm"))
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
