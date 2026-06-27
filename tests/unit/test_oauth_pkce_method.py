from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest
from pydantic import HttpUrl
from respx import MockRouter

from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.credentials import Credential, OAuthCredential
from authlm.errors import ReconnectionRequired
from authlm.providers.base import OAuthGrant


class _StubStore:
    def get(self, provider: str, alias: str) -> Credential | None:
        return None

    def set(self, credential: Credential) -> None:
        pass

    def delete(self, provider: str, alias: str) -> bool:
        return False

    def list(self) -> object:
        return iter(())

    def backend_name(self) -> str:
        return "stub"


def _token_response() -> dict[str, Any]:
    return {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "scope": "openid profile",
    }


def _make_callback_trigger(port: int, code: str):
    def open_browser(authorize_url: str) -> None:
        query = parse_qs(urlparse(authorize_url).query)
        state = query.get("state", [""])[0]
        callback_url = f"http://127.0.0.1:{port}/callback?code={code}&state={state}"
        urlopen(callback_url).read()

    return open_browser


def _method(
    *,
    http_client: httpx.AsyncClient,
    port: int,
    code: str = "AUTHCODE",
) -> OAuthPKCEMethod:
    return OAuthPKCEMethod(
        provider_id="openai",
        authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="test-client",
        scopes=("openid", "profile"),
        redirect_port=port,
        http_client=http_client,
        open_browser=_make_callback_trigger(port, code),
    )


@pytest.mark.asyncio
async def test_oauth_pkce_method_metadata() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, port=14550)
    assert method.id == "oauth_browser"
    assert method.label == "Browser OAuth (PKCE)"
    assert method.warning is None
    assert method.oauth_grant == OAuthGrant.AUTHORIZATION_CODE_PKCE


@pytest.mark.asyncio
async def test_connect_with_pkce_flow(respx_mock: MockRouter) -> None:
    port = 14555
    token_route = respx_mock.post("https://auth.openai.com/oauth/token").respond(
        200, json=_token_response()
    )

    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, port=port)
        cred = await method.connect(store=_StubStore())

    assert token_route.called
    assert isinstance(cred, OAuthCredential)
    assert cred.provider == "openai"
    assert cred.access_token == "ACCESS"
    assert cred.refresh_token == "REFRESH"
    assert "openid" in cred.scopes
    assert "profile" in cred.scopes
    request_body = token_route.calls.last.request.content.decode()
    assert "grant_type=authorization_code" in request_body
    assert "code=AUTHCODE" in request_body
    assert "redirect_uri=" in request_body
    assert "client_id=test-client" in request_body
    assert "code_verifier=" in request_body


@pytest.mark.asyncio
async def test_connect_handles_invalid_grant(respx_mock: MockRouter) -> None:
    port = 14556
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        400, json={"error": "invalid_grant"}
    )

    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, port=port)
        with pytest.raises(ReconnectionRequired):
            await method.connect(store=_StubStore())


@pytest.mark.asyncio
async def test_validate_accepts_oauth_credential() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, port=14558)
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert await method.validate(cred, force=False) is True


@pytest.mark.asyncio
async def test_validate_rejects_expired_credential() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, port=14559)
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    assert await method.validate(cred, force=False) is False
