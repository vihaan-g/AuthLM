from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import HttpUrl
from respx import MockRouter

from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.credentials import Credential, OAuthCredential
from authlm.errors import ReconnectionRequired
from authlm.providers.base import OAuthGrant
from authlm.stores.base import CredentialStore


class _StubStore(CredentialStore):
    def get(self, provider: str, alias: str) -> Credential | None:
        return None

    def set(self, credential: Credential) -> None:
        pass

    def delete(self, provider: str, alias: str) -> bool:
        return False

    def list(self) -> Iterator[tuple[str, str]]:
        return iter(())

    def backend_name(self) -> str:
        return "stub"


def _device_response(device_code: str = "DEVCODE") -> dict[str, Any]:
    return {
        "device_code": device_code,
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://auth.openai.com/codex/device",
        "expires_in": 900,
        "interval": 1,
    }


def _token_response() -> dict[str, Any]:
    return {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "scope": "openid",
    }


def _method(
    *,
    http_client: httpx.AsyncClient,
    on_prompt: Any = None,
) -> OAuthDeviceCodeMethod:
    return OAuthDeviceCodeMethod(
        provider_id="openai",
        device_code_url=HttpUrl(
            "https://auth.openai.com/api/accounts/deviceauth/usercode"
        ),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="cid",
        scopes=("openid",),
        on_prompt=on_prompt,
        poll_interval_seconds=0,
        poll_timeout_seconds=5.0,
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_oauth_device_method_metadata() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client)
    assert method.id == "oauth_device"
    assert method.label == "Device-code OAuth"
    assert method.warning is None
    assert method.oauth_grant == OAuthGrant.DEVICE_CODE


@pytest.mark.asyncio
async def test_connect_polls_until_authorized(respx_mock: MockRouter) -> None:
    device_route = respx_mock.post(
        "https://auth.openai.com/api/accounts/deviceauth/usercode"
    ).respond(200, json=_device_response())
    token_route = respx_mock.post("https://auth.openai.com/oauth/token").mock(
        side_effect=[
            httpx.Response(400, json={"error": "authorization_pending"}),
            httpx.Response(200, json=_token_response()),
        ]
    )

    prompts: list[tuple[str, str]] = []

    def on_prompt(uri: str, code: str) -> None:
        prompts.append((uri, code))

    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, on_prompt=on_prompt)
        cred = await method.connect(store=_StubStore())

    assert device_route.called
    assert token_route.call_count == 2
    assert isinstance(cred, OAuthCredential)
    assert cred.access_token == "ACCESS"
    assert prompts == [("https://auth.openai.com/codex/device", "ABCD-EFGH")]


@pytest.mark.asyncio
async def test_connect_handles_expired_token(respx_mock: MockRouter) -> None:
    respx_mock.post("https://auth.openai.com/api/accounts/deviceauth/usercode").respond(
        200, json=_device_response()
    )
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        400, json={"error": "expired_token"}
    )

    async with httpx.AsyncClient() as client:
        method = _method(http_client=client, on_prompt=lambda _u, _c: None)
        with pytest.raises(ReconnectionRequired):
            await method.connect(store=_StubStore())


@pytest.mark.asyncio
async def test_validate_accepts_oauth_credential() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client)
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_device",
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert await method.validate(cred, force=False) is True


@pytest.mark.asyncio
async def test_validate_rejects_expired_credential() -> None:
    async with httpx.AsyncClient() as client:
        method = _method(http_client=client)
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_device",
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    assert await method.validate(cred, force=False) is False


def test_device_method_with_on_prompt_returns_new_instance() -> None:
    captured: list[tuple[str, str]] = []

    def my_prompt(uri: str, code: str) -> None:
        captured.append((uri, code))

    method = OAuthDeviceCodeMethod(
        provider_id="openai",
        device_code_url=HttpUrl(
            "https://auth.openai.com/api/accounts/deviceauth/usercode"
        ),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="cid",
        scopes=("openid",),
        on_prompt=my_prompt,
        poll_interval_seconds=0,
        poll_timeout_seconds=5.0,
    )
    new_method = method.with_on_prompt(my_prompt)
    assert new_method is not method
    assert new_method._on_prompt is my_prompt  # noqa: SLF001
