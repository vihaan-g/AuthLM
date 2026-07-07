from __future__ import annotations

import httpx

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
