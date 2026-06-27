from __future__ import annotations

import pluggy
import pytest

import authlm.plugins as plugins
from authlm import hookspecs  # noqa: F401  # referenced via plugins.pm.hook


@pytest.fixture(autouse=True)
def _reset_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins, "_loaded", False)
    monkeypatch.setattr(plugins, "pm", None)


def test_load_plugins_creates_pm() -> None:
    plugins.load_plugins()
    assert plugins.pm is not None
    assert isinstance(plugins.pm, pluggy.PluginManager)


def test_load_plugins_adds_hookspecs() -> None:
    plugins.load_plugins()
    assert plugins.pm is not None
    assert hasattr(plugins.pm.hook, "register_providers")
    assert hasattr(plugins.pm.hook, "register_connection_methods")
    assert hasattr(plugins.pm.hook, "register_stores")


def test_load_plugins_idempotent() -> None:
    plugins.load_plugins()
    first = plugins.pm
    plugins.load_plugins()
    assert plugins.pm is first


def test_get_plugin_manager_loads() -> None:
    pm = plugins.get_plugin_manager()
    assert isinstance(pm, pluggy.PluginManager)
    assert hasattr(pm.hook, "register_providers")


def test_called_from_test_skips_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins, "_loaded", False)
    monkeypatch.setattr(plugins, "pm", None)
    plugins.load_plugins()
    assert plugins.pm is not None
    registered = set(plugins.pm._name2plugin)
    assert registered == set(plugins.DEFAULT_PLUGINS)


def test_broken_default_plugin_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins, "_loaded", False)
    monkeypatch.setattr(plugins, "pm", None)
    monkeypatch.setattr(plugins, "DEFAULT_PLUGINS", ("nonexistent.module.xyz",))
    plugins.load_plugins()
    assert plugins.pm is not None
    assert hasattr(plugins.pm.hook, "register_providers")
