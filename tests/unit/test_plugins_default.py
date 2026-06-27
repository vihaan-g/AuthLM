from __future__ import annotations

import pytest

import authlm.plugins as plugins
from authlm.plugins import load_plugins


@pytest.fixture(autouse=True)
def _reset_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins, "_loaded", False)
    monkeypatch.setattr(plugins, "pm", None)


def test_default_plugins_populated() -> None:
    assert len(plugins.DEFAULT_PLUGINS) == 4
    names = {name.split(".")[-1] for name in plugins.DEFAULT_PLUGINS}
    assert names == {"openai", "anthropic", "google", "openrouter"}


def test_load_plugins_registers_providers() -> None:
    load_plugins()
    assert plugins.pm is not None
    registered = list(plugins.pm.list_name_plugin())
    assert any("openai" in name for name, _ in registered)
    assert any("anthropic" in name for name, _ in registered)
    assert any("google" in name for name, _ in registered)
    assert any("openrouter" in name for name, _ in registered)
