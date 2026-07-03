from __future__ import annotations

import sys

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
