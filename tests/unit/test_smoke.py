from __future__ import annotations

import os

import authlm


def test_package_imports() -> None:
    assert authlm is not None


def test_version_is_string() -> None:
    assert isinstance(authlm.__version__, str)
    assert authlm.__version__ != ""


def test_env_isolation_active() -> None:
    assert os.environ["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
    assert "AUTHLM_USER_PATH" in os.environ
