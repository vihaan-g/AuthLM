from __future__ import annotations

from collections.abc import Callable, Sequence

import pluggy

import authlm.hookspecs as hookspecs
from authlm.hookspecs import hookimpl
from authlm.providers.base import ConnectionMethod, Provider


class _FakeProvider:
    @property
    def id(self) -> str:
        return "fake"

    @property
    def display_name(self) -> str:
        return "Fake"

    @property
    def docs_url(self) -> str | None:
        return None

    @property
    def logo_url(self) -> str | None:
        return None

    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        return []


class _FakePlugin:
    @hookimpl
    def register_providers(self, register: Callable[[Provider], None]) -> None:
        register(_FakeProvider())


def test_hookspecs_loaded_into_pm() -> None:
    pm = pluggy.PluginManager("authlm")
    pm.add_hookspecs(hookspecs)
    assert hasattr(pm.hook, "register_providers")
    assert hasattr(pm.hook, "register_connection_methods")
    assert hasattr(pm.hook, "register_stores")


def test_register_providers_hook_fires() -> None:
    pm = pluggy.PluginManager("authlm")
    pm.add_hookspecs(hookspecs)
    pm.register(_FakePlugin(), name="fake")
    collected: list[Provider] = []
    pm.hook.register_providers(register=collected.append)
    assert len(collected) == 1
    assert collected[0].id == "fake"


def test_register_providers_no_impls_returns_empty() -> None:
    pm = pluggy.PluginManager("authlm")
    pm.add_hookspecs(hookspecs)
    collected: list[Provider] = []
    result = pm.hook.register_providers(register=collected.append)
    assert result == []
    assert collected == []
