from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx
import pytest
from respx import MockRouter

from authlm.credentials import OAuthCredential
from authlm.providers.base import OAuthGrant, Provider
from authlm.providers.openai import OpenAIProvider
from authlm.stores.memory_store import MemoryStore


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
        m
        for m in p.connection_methods(include_warned=False)
        if m.id == "chatgpt_oauth_browser"
    )
    assert method.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE
    assert method.warning is None


def test_oauth_device_method_grant() -> None:
    p = _provider()
    method = next(
        m
        for m in p.connection_methods(include_warned=False)
        if m.id == "chatgpt_oauth_device"
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
    oauth_methods = [
        m for m in methods if m.id in ("chatgpt_oauth_browser", "chatgpt_oauth_device")
    ]
    assert len(oauth_methods) > 0
    for m in oauth_methods:
        if m.id == "chatgpt_oauth_browser":
            from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod

            assert isinstance(m, OAuthPKCEMethod)
        else:
            from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod

            assert isinstance(m, OAuthDeviceCodeMethod)
        assert m._client_id == "custom-client-id"  # noqa: SLF001


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


def test_openai_method_labels_match_spec() -> None:
    """OpenAI OAuth method labels match spec table."""
    from authlm.providers.openai import OpenAIProvider

    provider = OpenAIProvider(
        secret_prompt=lambda _p: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    labels = {m.id: m.label for m in methods}
    assert labels["api_key"] == "Manually enter API key"
    assert labels["chatgpt_oauth_browser"] == "ChatGPT Pro/Plus (browser)"
    assert labels["chatgpt_oauth_device"] == "ChatGPT Pro/Plus (headless)"


def test_connection_methods_accepts_http_client() -> None:
    """connection_methods() uses the provider's http_client when none is passed."""
    client = httpx.AsyncClient()
    provider = OpenAIProvider(secret_prompt=lambda _p: "", http_client=client)

    methods = list(provider.connection_methods(include_warned=True))
    for m in methods:
        if hasattr(m, "_http_client"):
            assert m._http_client is client

    assert provider._http_client is client


def test_openai_pkce_method_includes_codex_authorize_params() -> None:
    """The PKCE method carries the Codex-specific extra_authorize_params."""
    provider = OpenAIProvider(
        secret_prompt=lambda _p: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    pkce = next(m for m in methods if m.id == "chatgpt_oauth_browser")
    from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
    assert isinstance(pkce, OAuthPKCEMethod)
    params = pkce._extra_authorize_params  # noqa: SLF001
    assert params["codex_cli_simplified_flow"] == "true"
    assert params["originator"] == "codex_cli_rs"
    assert params["id_token_add_organizations"] == "true"


def test_openai_device_method_uses_json_content_type() -> None:
    """OpenAI device-code method is configured for JSON, not form-encoded."""
    provider = OpenAIProvider(
        secret_prompt=lambda _p: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    device = next(m for m in methods if m.id == "chatgpt_oauth_device")
    from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
    assert isinstance(device, OAuthDeviceCodeMethod)
    assert device._device_code_content_type == "application/json"  # noqa: SLF001


def test_openai_pkce_method_uses_codex_fixed_redirect_uri() -> None:
    """OpenAI PKCE method is initialized with the pinned Codex redirect URI."""
    provider = OpenAIProvider(
        secret_prompt=lambda _prompt: "", http_client=httpx.AsyncClient()
    )
    methods = provider.connection_methods(include_warned=False)
    pkce = next(method for method in methods if method.id == "chatgpt_oauth_browser")
    from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
    assert isinstance(pkce, OAuthPKCEMethod)
    assert pkce._fixed_redirect_uri == "http://localhost:1455/auth/callback"  # noqa: SLF001


@pytest.mark.asyncio
async def test_openai_device_flow_uses_codex_endpoints(
    respx_mock: MockRouter,
) -> None:
    usercode_route = respx_mock.post(
        "https://auth.openai.com/api/accounts/deviceauth/usercode"
    ).respond(
        200,
        json={
            "device_auth_id": "device-auth-id",
            "user_code": "CODE-12345",
            "interval": "0",
        },
    )
    poll_route = respx_mock.post(
        "https://auth.openai.com/api/accounts/deviceauth/token"
    ).mock(
        side_effect=[
            httpx.Response(404),
            httpx.Response(
                200,
                json={
                    "authorization_code": "authorization-code",
                    "code_challenge": "codex-challenge",
                    "code_verifier": "codex-verifier",
                },
            ),
        ]
    )
    token_route = respx_mock.post("https://auth.openai.com/oauth/token").respond(
        200,
        json={
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "expires_in": 3600,
        },
    )
    prompts: list[tuple[str, str]] = []

    def on_prompt(uri: str, user_code: str) -> None:
        prompts.append((uri, user_code))

    async with httpx.AsyncClient() as client:
        provider = OpenAIProvider(secret_prompt=lambda _prompt: "", http_client=client)
        device = next(
            method
            for method in provider.connection_methods(include_warned=False)
            if method.id == "chatgpt_oauth_device"
        )
        from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
        assert isinstance(device, OAuthDeviceCodeMethod)
        credential = await device.with_on_prompt(on_prompt).connect(store=MemoryStore())

    assert isinstance(credential, OAuthCredential)
    assert prompts == [("https://auth.openai.com/codex/device", "CODE-12345")]
    assert json.loads(usercode_route.calls.last.request.content) == {
        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann"
    }
    assert json.loads(poll_route.calls.last.request.content) == {
        "device_auth_id": "device-auth-id",
        "user_code": "CODE-12345",
    }
    request_body = token_route.calls.last.request.content.decode()
    assert "grant_type=authorization_code" in request_body
    assert "code=authorization-code" in request_body
    assert "code_verifier=codex-verifier" in request_body
    assert (
        "redirect_uri=https%3A%2F%2Fauth.openai.com%2Fdeviceauth%2Fcallback"
        in request_body
    )
