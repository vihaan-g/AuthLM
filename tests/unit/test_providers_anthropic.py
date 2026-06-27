from __future__ import annotations

import httpx

from authlm.providers.anthropic import ANTHROPIC_CLAUDE_PRO_WARNING, AnthropicProvider
from authlm.providers.base import OAuthGrant, Provider


def _provider() -> AnthropicProvider:
    return AnthropicProvider(
        secret_prompt=lambda _p: "sk-test",
        http_client=httpx.AsyncClient(),
    )


def test_metadata() -> None:
    p = _provider()
    assert p.id == "anthropic"
    assert p.display_name == "Anthropic"
    assert "anthropic.com" in p.docs_url


def test_default_methods_excludes_warned() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    assert {m.id for m in methods} == {"api_key"}


def test_include_warned_returns_three() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=True)
    ids = {m.id for m in methods}
    assert ids == {"api_key", "claude_pro_oauth_browser", "claude_pro_oauth_device"}


def test_claude_pro_oauth_methods_have_warning() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=True)
    for m in methods:
        if m.id in {"claude_pro_oauth_browser", "claude_pro_oauth_device"}:
            assert m.warning is not None
            assert "Anthropic" in m.warning or "ToS" in m.warning


def test_api_key_method_has_no_warning() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=True)
    api_key = next(m for m in methods if m.id == "api_key")
    assert api_key.warning is None


def test_oauth_browser_grant() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=True)
    m = next(m for m in methods if m.id == "claude_pro_oauth_browser")
    assert m.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE


def test_oauth_device_grant() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=True)
    m = next(m for m in methods if m.id == "claude_pro_oauth_device")
    assert m.oauth_grant == OAuthGrant.DEVICE_CODE


def test_warning_constant_mentions_anthropic() -> None:
    assert "Anthropic" in ANTHROPIC_CLAUDE_PRO_WARNING


def test_provider_satisfies_protocol() -> None:
    assert isinstance(_provider(), Provider)
