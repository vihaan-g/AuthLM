from __future__ import annotations

import logging
import os
from pathlib import Path

import keyring
from keyring.backends import fail as _fail
from keyring.backends import null as _null
from platformdirs import PlatformDirs

from authlm.errors import AuthLMError
from authlm.stores.base import CredentialStore
from authlm.stores.encrypted_file_store import EncryptedFileStore
from authlm.stores.env_store import _ENV_VAR_MAP, EnvStore
from authlm.stores.keyring_store import KeyringStore
from authlm.stores.memory_store import MemoryStore

_log = logging.getLogger(__name__)

__all__ = [
    "CredentialStore",
    "EncryptedFileStore",
    "EnvStore",
    "KeyringStore",
    "MemoryStore",
    "get_default_store",
]


def _user_data_path() -> Path:
    env_path = os.environ.get("AUTHLM_USER_PATH")
    if env_path is not None:
        return Path(env_path)
    return PlatformDirs("authlm", appauthor=False).user_data_path


def get_default_store() -> CredentialStore:
    """Auto-select and return a CredentialStore.

    Selection order:
    1. ``AUTHLM_STORE`` env var (explicit override).
    2. KeyringStore if a real keyring backend is available.
    3. EnvStore with a warning log.
    """
    store_name = os.environ.get("AUTHLM_STORE")
    if store_name is not None:
        if store_name == "keyring":
            return KeyringStore(index_path=_user_data_path() / "keyring-index.json")
        if store_name == "encrypted_file":
            passphrase = os.environ.get("AUTHLM_PASSPHRASE")
            if passphrase is None:
                raise AuthLMError(
                    "AUTHLM_STORE=encrypted_file requires AUTHLM_PASSPHRASE"
                )
            return EncryptedFileStore(
                path=_user_data_path() / "credentials.enc.json",
                passphrase=passphrase,
                iterations=600_000,
            )
        if store_name == "env":
            return EnvStore(mapping=_ENV_VAR_MAP)
        if store_name == "memory":
            return MemoryStore()
        raise AuthLMError(f"Unknown AUTHLM_STORE value: {store_name}")

    kr = keyring.get_keyring()
    if not isinstance(kr, (_fail.Keyring, _null.Keyring)):
        return KeyringStore(index_path=_user_data_path() / "keyring-index.json")

    _log.warning(
        "No keyring backend available; using EnvStore (credentials won't persist)"
    )
    return EnvStore(mapping=_ENV_VAR_MAP)
