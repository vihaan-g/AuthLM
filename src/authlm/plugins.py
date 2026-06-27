from __future__ import annotations

import importlib
import logging
import sys

import pluggy

from authlm import hookspecs

_log = logging.getLogger(__name__)

pm: pluggy.PluginManager | None = None
_loaded: bool = False
DEFAULT_PLUGINS: tuple[str, ...] = (
    "authlm.providers.openai",
    "authlm.providers.anthropic",
    "authlm.providers.google",
    "authlm.providers.openrouter",
)


def load_plugins() -> None:
    """Initialize the plugin manager and load all default plugins.

    Idempotent: safe to call multiple times. Skips setuptools entry-point
    loading when ``sys._called_from_test`` is set (test isolation).
    """
    global _loaded, pm
    if _loaded:
        return
    _loaded = True
    pm = pluggy.PluginManager("authlm")
    pm.add_hookspecs(hookspecs)
    if not getattr(sys, "_called_from_test", False):
        pm.load_setuptools_entrypoints("authlm")
    for plugin_name in DEFAULT_PLUGINS:
        try:
            module = importlib.import_module(plugin_name)
        except ImportError:
            _log.warning("Failed to import plugin %s", plugin_name, exc_info=True)
            continue
        pm.register(module, plugin_name)


def get_plugin_manager() -> pluggy.PluginManager:
    """Return the singleton PluginManager, loading plugins if needed."""
    if pm is None:
        load_plugins()
    assert pm is not None
    return pm
