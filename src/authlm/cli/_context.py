from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import PlatformDirs

from authlm.errors import AuthLMError
from authlm.stores import (
    EncryptedFileStore,
    EnvStore,
    KeyringStore,
    MemoryStore,
    get_default_store,
)
from authlm.stores.base import CredentialStore
from authlm.stores.env_store import _ENV_VAR_MAP


def get_store(*, store_name: str | None) -> CredentialStore:
    """Return a CredentialStore for the given store name.

    When ``store_name`` is ``None``, delegates to
    ``authlm.stores.get_default_store`` (which honors the ``AUTHLM_STORE``
    env var and falls back to keyring-or-env). When ``store_name`` is
    given, the named store is built directly, bypassing the env var.
    """
    if store_name is None:
        return get_default_store()
    if store_name == "memory":
        return MemoryStore()
    if store_name == "env":
        return EnvStore(mapping=_ENV_VAR_MAP)
    if store_name == "keyring":
        return KeyringStore(index_path=_user_data_path() / "keyring-index.json")
    if store_name == "encrypted_file":
        passphrase = os.environ.get("AUTHLM_PASSPHRASE")
        if passphrase is None:
            raise AuthLMError("--store=encrypted_file requires AUTHLM_PASSPHRASE")
        return EncryptedFileStore(
            path=_user_data_path() / "credentials.enc.json",
            passphrase=passphrase,
            iterations=600_000,
        )
    raise AuthLMError(f"Unknown --store value: {store_name}")


def is_tty() -> bool:
    """Return True if stdin is a terminal."""
    return bool(sys.stdin.isatty())


def _user_data_path() -> Path:
    env_path = os.environ.get("AUTHLM_USER_PATH")
    if env_path is not None:
        return Path(env_path)
    return PlatformDirs("authlm", appauthor=False).user_data_path
