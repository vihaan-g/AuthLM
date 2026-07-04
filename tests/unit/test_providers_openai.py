from __future__ import annotations

from urllib.parse import urlparse

import httpx
import pytest

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
    assert host is not None
    assert host in ("openai.com", "platform.openai.com")


def test_default_methods() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    ids = {m.id for m in methods}
    assert ids == {"api_key", "chatgpt_oauth_browser", "chatgpt_oauth_device"}


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
        m for m in p.connection_methods(include_warned=False) if m.id == "chatgpt_oauth_browser"
    )
    assert method.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE
    assert method.warning is None


def test_oauth_device_method_grant() -> None:
    p = _provider()
    method = next(
        m for m in p.connection_methods(include_warned=False) if m.id == "chatgpt_oauth_device"
    )
    assert method.oauth_grant == OAuthGrant.DEVICE_CODE
    assert method.warning is None


def test_provider_satisfies_protocol() -> None:
    assert isinstance(_provider(), Provider)


def test_openai_provider_uses_env_var_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUTHLM_OPENAI_CLIENT_ID overrides the default client ID."""
    monkeypatch.setenv("AUTHLM_OPENAI_CLIENT_ID", "custom-client-id")
    from authlm.providers.openai import OpenAIProvider

    provider = OpenAIProvider(
        secret_prompt=lambda _p: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    oauth_methods = [m for m in methods if m.id in ("chatgpt_oauth_browser", "chatgpt_oauth_device")]
    assert len(oauth_methods) > 0
    for m in oauth_methods:
        assert m._client_id == "custom-client-id"  # type: ignore[union-attr]  # noqa: SLF001


def test_openai_method_ids_match_spec() -> None:
    """OpenAI method IDs match spec: chatgpt_oauth_browser, chatgpt_oauth_device."""
    from authlm.providers.openai import OpenAIProvider

    provider = OpenAIProvider(
        secret_prompt=lambda _p: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    ids = {m.id for m in methods}
    assert "api_key" in ids
    assert "chatgpt_oauth_browser" in ids
    assert "chatgpt_oauth_device" in ids
