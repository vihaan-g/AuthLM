from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import HttpUrl
from respx import MockRouter

from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.credentials import OAuthCredential
from authlm.errors import (
    ConnectionTimeout,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.providers.base import OAuthGrant
from authlm.stores.memory_store import MemoryStore


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
        cred = await method.connect(store=MemoryStore())

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
            await method.connect(store=MemoryStore())


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


@pytest.mark.asyncio
async def test_connect_handles_slow_down() -> None:
    import httpx

    _calls = 0

    def slow_down_sequence(request: httpx.Request) -> httpx.Response:
        nonlocal _calls
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                    "interval": 1,
                    "expires_in": 60,
                },
            )
        _calls += 1
        if _calls == 1:
            return httpx.Response(400, json={"error": "slow_down"})
        if _calls == 2:
            return httpx.Response(400, json={"error": "authorization_pending"})
        return httpx.Response(
            200,
            json={
                "access_token": "at-1",
                "refresh_token": "rt-1",
                "expires_in": 3600,
            },
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=30.0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(slow_down_sequence)
        ),
    )
    cred = await method.connect(store=MemoryStore())
    assert isinstance(cred, OAuthCredential)


@pytest.mark.asyncio
async def test_connect_times_out_when_always_authorization_pending() -> None:
    store = MemoryStore()

    def _always_pending(request: httpx.Request) -> httpx.Response:
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                },
            )
        return httpx.Response(400, json={"error": "authorization_pending"})

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=0.5,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_always_pending)),
    )
    with pytest.raises(ConnectionTimeout):
        await method.connect(store=store)


@pytest.mark.asyncio
async def test_non_json_device_code_response_raises_token_error() -> None:
    """Non-JSON 200 from device-code endpoint raises TokenEndpointError."""

    def _html_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Error</html>")

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_html_response)),
    )
    with pytest.raises(TokenEndpointError, match="non-JSON"):
        await method.connect(store=MemoryStore())


@pytest.mark.asyncio
async def test_device_code_request_is_form_encoded() -> None:
    """Device-code authorization request sends form-encoded body, not JSON."""
    captured_content_type: list[str] = []

    def _capture_request(request: httpx.Request) -> httpx.Response:
        captured_content_type.append(request.headers.get("content-type", ""))
        return httpx.Response(
            200,
            json={
                "device_code": "dc-1",
                "user_code": "UC-1",
                "verification_uri": "https://example.com/activate",
            },
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_capture_request)),
    )
    await method._request_device_code()  # type: ignore[reportPrivateUsage]  # noqa: SLF001
    assert len(captured_content_type) == 1
    assert "application/x-www-form-urlencoded" in captured_content_type[0]


@pytest.mark.asyncio
async def test_device_code_slow_down_retries() -> None:
    """slow_down error triggers another poll, eventually succeeding."""
    poll_count = 0

    def _tracking_transport(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                    "interval": 0,
                    "expires_in": 30,
                },
            )
        poll_count += 1
        if poll_count == 1:
            return httpx.Response(400, json={"error": "slow_down"})
        return httpx.Response(
            200,
            json={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=30.0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(_tracking_transport)
        ),
    )
    await method.connect(store=MemoryStore())
    assert poll_count == 2


@pytest.mark.asyncio
async def test_device_code_slow_down_increases_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """slow_down increases the poll interval by 5s on the next sleep."""
    sleep_calls: list[float] = []

    async def _tracking_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "authlm.connection_methods.oauth_device.asyncio.sleep",
        _tracking_sleep,
    )

    poll_count = 0

    def _transport(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                    "interval": 0,
                    "expires_in": 30,
                },
            )
        poll_count += 1
        if poll_count == 1:
            return httpx.Response(400, json={"error": "authorization_pending"})
        if poll_count == 2:
            return httpx.Response(400, json={"error": "slow_down"})
        return httpx.Response(
            200,
            json={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=30.0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_transport)),
    )
    await method.connect(store=MemoryStore())

    assert len(sleep_calls) >= 2
    # First poll after authorization_pending: normal interval (0.1)
    assert sleep_calls[0] == pytest.approx(0.1)
    # Second poll after slow_down: interval + 5.0
    assert sleep_calls[1] == pytest.approx(5.1)


@pytest.mark.asyncio
async def test_device_code_slow_down_is_persistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple slow_down responses cumulatively increase the interval."""
    sleep_calls: list[float] = []

    async def _tracking_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "authlm.connection_methods.oauth_device.asyncio.sleep",
        _tracking_sleep,
    )

    poll_count = 0

    def _transport(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                    "interval": 0,
                    "expires_in": 30,
                },
            )
        poll_count += 1
        if poll_count <= 2:
            return httpx.Response(400, json={"error": "slow_down"})
        return httpx.Response(
            200,
            json={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=30.0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_transport)),
    )
    await method.connect(store=MemoryStore())

    assert len(sleep_calls) == 2
    # First slow_down: interval becomes 0.1 + 5.0 = 5.1
    assert sleep_calls[0] == pytest.approx(5.1)
    # Second slow_down: interval becomes 5.1 + 5.0 = 10.1
    assert sleep_calls[1] == pytest.approx(10.1)


@pytest.mark.asyncio
async def test_device_code_response_expires_in_caps_timeout() -> None:
    """When expires_in from device response is less than poll_timeout, it caps."""
    poll_count = 0

    def _timeout_transport(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if "device/code" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-1",
                    "user_code": "UC-1",
                    "verification_uri": "https://example.com/activate",
                    "expires_in": 0.3,
                },
            )
        poll_count += 1
        return httpx.Response(400, json={"error": "authorization_pending"})

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        poll_interval_seconds=0.1,
        poll_timeout_seconds=30.0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(_timeout_transport)
        ),
    )
    with pytest.raises(ConnectionTimeout):
        await method.connect(store=MemoryStore())
    assert poll_count <= 5


@pytest.mark.asyncio
async def test_request_device_code_network_error_raises_refresh_failed() -> None:
    """_request_device_code() wraps httpx.HTTPError in RefreshFailed."""

    def _network_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_network_error)),
    )
    with pytest.raises(RefreshFailed, match="network error"):
        await method._request_device_code()  # type: ignore[reportPrivateUsage]  # noqa: SLF001


@pytest.mark.asyncio
async def test_request_device_code_503_raises_refresh_failed() -> None:
    """_request_device_code() raises RefreshFailed on 503, not TokenEndpointError."""

    def _server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server_error"})

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_server_error)),
    )
    with pytest.raises(RefreshFailed):
        await method._request_device_code()  # type: ignore[reportPrivateUsage]  # noqa: SLF001


@pytest.mark.asyncio
async def test_device_code_request_is_json_when_configured() -> None:
    """When device_code_content_type='application/json', request body is JSON."""
    captured_content_type: list[str] = []

    def _capture_request(request: httpx.Request) -> httpx.Response:
        captured_content_type.append(request.headers.get("content-type", ""))
        return httpx.Response(
            200,
            json={
                "device_code": "dc-1",
                "user_code": "UC-1",
                "verification_uri": "https://example.com/activate",
            },
        )

    method = OAuthDeviceCodeMethod(
        provider_id="test",
        device_code_url=HttpUrl("https://example.com/device/code"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        device_code_content_type="application/json",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_capture_request)),
    )
    await method._request_device_code()  # type: ignore[reportPrivateUsage]  # noqa: SLF001
    assert len(captured_content_type) == 1
    assert "application/json" in captured_content_type[0]
