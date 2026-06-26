from __future__ import annotations

from collections.abc import Callable

from pluggy import HookimplMarker, HookspecMarker

from authlm.providers.base import ConnectionMethod, Provider
from authlm.stores.base import CredentialStore

hookspec = HookspecMarker("authlm")
hookimpl = HookimplMarker("authlm")


@hookspec
def register_providers(register: Callable[[Provider], None]) -> None:
    """Register Provider instances.

    ``register(provider: Provider)`` adds a provider to the registry.
    """


@hookspec
def register_connection_methods(
    register: Callable[[ConnectionMethod, str], None],
) -> None:
    """Register ConnectionMethod instances.

    ``register(method: ConnectionMethod, provider_id: str)`` adds a method.
    """


@hookspec
def register_stores(
    register: Callable[[CredentialStore, str], None],
) -> None:
    """Register CredentialStore implementations.

    ``register(store: CredentialStore, name: str)`` adds a store backend.
    """
