from __future__ import annotations

from authlm.providers.openrouter import OpenRouterProvider


def _provider() -> OpenRouterProvider:
    return OpenRouterProvider(secret_prompt=lambda _p: "sk-or-test")


def test_metadata() -> None:
    p = _provider()
    assert p.id == "openrouter"
    assert p.display_name == "OpenRouter"
    assert "openrouter.ai" in p.docs_url


def test_only_api_key_method() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    assert len(methods) == 1
    assert methods[0].id == "api_key"
    assert methods[0].oauth_grant is None
    assert methods[0].warning is None
