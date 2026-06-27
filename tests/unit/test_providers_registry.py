from __future__ import annotations

import pytest

from authlm.errors import AuthLMError
from authlm.providers.base import Provider
from authlm.providers.registry import get_method, get_provider, list_providers


def test_list_providers_returns_four() -> None:
    providers = list_providers()
    ids = {p.id for p in providers}
    assert ids == {"openai", "anthropic", "google", "openrouter"}


def test_get_provider_known() -> None:
    p = get_provider("openai")
    assert p.id == "openai"
    assert p.display_name == "OpenAI"


def test_get_provider_unknown_raises() -> None:
    with pytest.raises(AuthLMError):
        get_provider("nonexistent")


def test_get_method_known() -> None:
    method = get_method("openai", "api_key")
    assert method.id == "api_key"


def test_get_method_unknown_raises() -> None:
    with pytest.raises(AuthLMError):
        get_method("openai", "nonexistent_method")


def test_get_method_includes_warned() -> None:
    method = get_method("anthropic", "claude_pro_oauth_browser")
    assert method.id == "claude_pro_oauth_browser"


def test_all_providers_satisfy_protocol() -> None:
    for p in list_providers():
        assert isinstance(p, Provider)
