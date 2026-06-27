from __future__ import annotations

from typing import Any

import pytest
from respx import MockRouter

from authlm.connection_methods._oauth_helpers import redact_body
from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.errors import TokenEndpointError
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


@pytest.mark.asyncio
async def test_validate_redacts_access_token_in_400_body(
    respx_mock: MockRouter,
) -> None:
    secret = "AKIA-real-token-1234567890"
    respx_mock.get("https://api.openai.com/v1/models").respond(
        400, text=f'{{"error":"invalid_token","access_token":"{secret}"}}'
    )
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    with pytest.raises(TokenEndpointError) as exc_info:
        await validate(cred, force=False)
    msg = str(exc_info.value)
    assert secret not in msg
    assert "[REDACTED]" in msg


@pytest.mark.asyncio
async def test_validate_redacts_bearer_token_in_400_body(
    respx_mock: MockRouter,
) -> None:
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    respx_mock.get("https://api.openai.com/v1/models").respond(
        400, text=f"Bearer {token}"
    )
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    with pytest.raises(TokenEndpointError) as exc_info:
        await validate(cred, force=False)
    msg = str(exc_info.value)
    assert token not in msg
    assert "[REDACTED]" in msg


def test_redact_body_truncates_to_200_chars() -> None:
    redacted = redact_body("x" * 500)
    assert len(redacted) <= 200
