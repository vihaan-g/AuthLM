from __future__ import annotations

import httpx

from authlm.connection_methods.api_key import _default_secret_prompt
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.providers.base import OAuthGrant
from authlm.providers.google import GoogleProvider


def _provider() -> GoogleProvider:
    return GoogleProvider(
        secret_prompt=lambda _p: "AIza-test",
        http_client=httpx.AsyncClient(),
    )


def test_metadata() -> None:
    p = _provider()
    assert p.id == "google"
    assert p.display_name == "Google AI"
    assert p.docs_url is not None
    assert "google" in p.docs_url


def test_default_methods() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    ids = {m.id for m in methods}
    assert ids == {"api_key", "oauth_browser"}


def test_no_device_method() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    assert not any(m.oauth_grant == OAuthGrant.DEVICE_CODE for m in methods)


def test_api_key_method_has_no_warning() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    api_key = next(m for m in methods if m.id == "api_key")
    assert api_key.warning is None


def test_oauth_method_uses_pkce() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    oauth = next(m for m in methods if m.id == "oauth_browser")
    assert oauth.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE
    assert oauth.warning is None
    assert oauth.label == "Google AI Studio (browser)"


def test_connection_methods_accepts_http_client() -> None:
    """connection_methods() reuses the provider's http_client."""
    client = httpx.AsyncClient()
    provider = GoogleProvider(secret_prompt=lambda _p: "", http_client=client)

    methods = list(provider.connection_methods(include_warned=False))
    for m in methods:
        if hasattr(m, "_http_client"):
            assert m._http_client is client

    assert provider._http_client is client  # noqa: SLF001


def test_google_provider_oauth_browser_method() -> None:
    """Google provider exposes an oauth_browser PKCE method with scopes."""
    provider = GoogleProvider(
        secret_prompt=_default_secret_prompt,
        http_client=httpx.AsyncClient(),
    )
    methods = list(provider.connection_methods(include_warned=True))
    oauth_methods = [m for m in methods if m.oauth_grant is not None]
    assert len(oauth_methods) == 1
    pkce = oauth_methods[0]
    assert pkce.id == "oauth_browser"
    assert pkce.label == "Google AI Studio (browser)"
    assert pkce.warning is None
    assert pkce.oauth_grant is not None
    assert isinstance(pkce, OAuthPKCEMethod)
    assert len(pkce._scopes) > 0  # noqa: SLF001
    assert "openid" in pkce._scopes  # noqa: SLF001


def test_connection_methods_lazy_http_client() -> None:
    """connection_methods() passes None for http_client when none is configured."""
    provider = GoogleProvider(secret_prompt=lambda _p: "")
    methods = list(provider.connection_methods(include_warned=True))
    for m in methods:
        if hasattr(m, "_http_client"):
            assert m._http_client is None  # noqa: SLF001
