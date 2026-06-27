from __future__ import annotations

from urllib.parse import urlparse

import httpx

from authlm.providers.base import OAuthGrant, Provider
from authlm.providers.openai import OpenAIProvider


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        secret_prompt=lambda _p: "sk-test",
        http_client=httpx.AsyncClient(),
    )


def test_metadata() -> None:
    p = _provider()
    assert p.id == "openai"
    assert p.display_name == "OpenAI"
    assert p.docs_url is not None
    host = urlparse(p.docs_url).hostname
    assert host is not None and host.endswith("openai.com")


def test_default_methods() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    ids = {m.id for m in methods}
    assert ids == {"api_key", "oauth_browser", "oauth_device"}


def test_api_key_method_warning() -> None:
    p = _provider()
    api_key = next(
        m for m in p.connection_methods(include_warned=False) if m.id == "api_key"
    )
    assert api_key.warning is None
    assert api_key.oauth_grant is None


def test_oauth_browser_method_grant() -> None:
    p = _provider()
    method = next(
        m for m in p.connection_methods(include_warned=False) if m.id == "oauth_browser"
    )
    assert method.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE
    assert method.warning is None


def test_oauth_device_method_grant() -> None:
    p = _provider()
    method = next(
        m for m in p.connection_methods(include_warned=False) if m.id == "oauth_device"
    )
    assert method.oauth_grant == OAuthGrant.DEVICE_CODE
    assert method.warning is None


def test_provider_satisfies_protocol() -> None:
    assert isinstance(_provider(), Provider)
