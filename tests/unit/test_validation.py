from __future__ import annotations

from typing import Any

import pytest
from respx import MockRouter

from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.validation import _is_warned, validate


@pytest.mark.asyncio
async def test_validate_api_key_openai_success(respx_mock: MockRouter) -> None:
    respx_mock.get("https://api.openai.com/v1/models").respond(
        200, json={"data": [{"id": "gpt-4o"}]}
    )
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    assert await validate(cred, force=False) is True


@pytest.mark.asyncio
async def test_validate_api_key_anthropic_success(respx_mock: MockRouter) -> None:
    respx_mock.get("https://api.anthropic.com/v1/models").respond(
        200, json={"data": [{"id": "claude-3-5-sonnet"}]}
    )
    cred = ApiKeyCredential(
        provider="anthropic", alias="default", method_id="api_key", secret="sk-test"
    )
    assert await validate(cred, force=False) is True


@pytest.mark.asyncio
async def test_validate_api_key_returns_false_on_401(respx_mock: MockRouter) -> None:
    respx_mock.get("https://api.openai.com/v1/models").respond(401, json={})
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="bad"
    )
    assert await validate(cred, force=False) is False


@pytest.mark.asyncio
async def test_validate_oauth_uses_bearer_token(respx_mock: MockRouter) -> None:
    captured: dict[str, str] = {}

    def side_effect(request: Any) -> Any:
        captured["auth"] = request.headers.get("Authorization", "")
        from httpx import Response

        return Response(200, json={"data": []})

    respx_mock.get("https://api.openai.com/v1/models").mock(side_effect=side_effect)
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="ACCESS",
        refresh_token=None,
        expires_at=None,
    )
    assert await validate(cred, force=False) is True
    assert captured["auth"] == "Bearer ACCESS"


@pytest.mark.asyncio
async def test_validate_warned_method_refuses_without_force() -> None:
    cred = ApiKeyCredential(
        provider="anthropic",
        alias="default",
        method_id="claude_pro_oauth_browser",
        secret="ignored",
    )
    with pytest.raises(PermissionError):
        await validate(cred, force=False)


@pytest.mark.asyncio
async def test_validate_warned_method_works_with_force(respx_mock: MockRouter) -> None:
    respx_mock.get("https://api.anthropic.com/v1/models").respond(
        200, json={"data": []}
    )
    cred = ApiKeyCredential(
        provider="anthropic",
        alias="default",
        method_id="claude_pro_oauth_browser",
        secret="secret",
    )
    assert await validate(cred, force=True) is True


@pytest.mark.asyncio
async def test_validate_unknown_provider_returns_false() -> None:
    cred = ApiKeyCredential(
        provider="unknown", alias="default", method_id="api_key", secret="x"
    )
    assert await validate(cred, force=False) is False


def test_is_warned_helper() -> None:
    assert _is_warned("claude_pro_oauth_browser") is True
    assert _is_warned("claude_pro_oauth_device") is True
    assert _is_warned("api_key") is False
    assert _is_warned("oauth_browser") is False
