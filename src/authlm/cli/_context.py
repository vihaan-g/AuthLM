from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import PlatformDirs

from authlm.metadata import MetadataStore
from authlm.stores import build_store, get_default_store
from authlm.stores.base import CredentialStore


def get_store(*, store_name: str | None) -> CredentialStore:
    """Return a CredentialStore for the given store name.

    When ``store_name`` is ``None``, delegates to
    ``authlm.stores.get_default_store`` (which honors the ``AUTHLM_STORE``
    env var and falls back to keyring-or-env). When ``store_name`` is
    given, the named store is built directly, bypassing the env var.
    """
    if store_name is None:
        return get_default_store()
    return build_store(store_name=store_name)


def is_tty() -> bool:
    """Return True if stdin is a terminal."""
    return bool(sys.stdin.isatty())


def get_metadata_path(override: Path | None) -> Path:
    """Resolve metadata path: explicit override > env var > default."""
    if override is not None:
        return override
    env = os.environ.get("AUTHLM_METADATA_PATH")
    if env is not None:
        return Path(env)
    env_user_path = os.environ.get("AUTHLM_USER_PATH")
    if env_user_path is not None:
        return Path(env_user_path) / "metadata.json"
    return PlatformDirs("authlm", appauthor=False).user_data_path / "metadata.json"


def get_metadata_store(metadata_path: Path | None) -> MetadataStore:
    """Build a MetadataStore with default path resolution."""
    return MetadataStore(path=get_metadata_path(metadata_path))
