from __future__ import annotations

from http.server import HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest
from pydantic import HttpUrl
from respx import MockRouter

from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.credentials import OAuthCredential
from authlm.errors import (
    AuthLMError,
    ConnectionTimeout,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.providers.base import OAuthGrant
from authlm.stores.memory_store import MemoryStore


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
        cred = await method.connect(store=MemoryStore())

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
            await method.connect(store=MemoryStore())


def test_pkce_method_with_open_browser_returns_new_instance() -> None:
    def my_open(url: str) -> None:
        pass

    method = OAuthPKCEMethod(
        provider_id="openai",
        authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="cid",
        scopes=("openid",),
        redirect_port=14999,
    )
    new_method = method.with_open_browser(my_open)
    assert new_method is not method
    assert new_method._open_browser is my_open  # noqa: SLF001


@pytest.mark.asyncio
async def test_handler_rejects_wrong_state() -> None:
    """The loopback Handler returns 400 when state doesn't match."""
    from urllib.error import HTTPError

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
    )

    captured: dict[str, str] = {}
    server = method._start_loopback(captured, "expected-state")  # type: ignore[reportPrivateUsage]  # noqa: SLF001
    port = server.server_address[1]
    try:
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"http://127.0.0.1:{port}/callback?state=wrong&code=testcode")
        assert exc_info.value.code == 400
        assert "code" not in captured
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_handler_returns_denied_html() -> None:
    """The loopback Handler returns 200 + denial HTML when user denies."""
    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
    )

    captured: dict[str, str] = {}
    server = method._start_loopback(captured, "expected-state")  # type: ignore[reportPrivateUsage]  # noqa: SLF001
    port = server.server_address[1]
    try:
        response = urlopen(
            f"http://127.0.0.1:{port}/callback"
            "?error=access_denied&state=expected-state"
        )
        assert response.status == 200
        body = response.read().decode()
        assert "denied" in body.lower()
        assert "code" not in captured
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_port_collision_raises_authlm_error() -> None:
    """When the loopback factory raises OSError, raise AuthLMError."""

    def _failing_factory(addr: tuple[str, int], handler: Any) -> HTTPServer:
        raise OSError("Address already in use")

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=14597,
        loopback_factory=_failing_factory,
    )

    with pytest.raises(AuthLMError, match="in use"):
        method._start_loopback({}, "state")  # type: ignore[reportPrivateUsage]  # noqa: SLF001


@pytest.mark.asyncio
async def test_pkce_timeout_raises_connection_timeout() -> None:
    """PKCE flow raises ConnectionTimeout when callback never arrives."""
    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
    )
    captured: dict[str, str] = {}
    with pytest.raises(ConnectionTimeout):
        await method._wait_for_code(captured, timeout=0.01)  # type: ignore[reportPrivateUsage]  # noqa: SLF001


@pytest.mark.asyncio
async def test_non_json_token_response_raises_token_error() -> None:
    """Non-JSON 200 from token endpoint raises TokenEndpointError."""

    def _html_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Error</html>")

    from authlm.connection_methods._oauth_helpers import PKCEPair

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_html_response)),
    )
    pair = PKCEPair(verifier="test-verifier", challenge="test-challenge")
    with pytest.raises(TokenEndpointError, match="non-JSON"):
        await method._exchange_code(  # type: ignore[reportPrivateUsage]  # noqa: SLF001
            code="test-code", pair=pair, redirect_uri="http://127.0.0.1:0/callback"
        )


@pytest.mark.asyncio
async def test_exchange_code_network_error_raises_refresh_failed() -> None:
    """_exchange_code() wraps httpx.HTTPError in RefreshFailed."""

    def _network_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    from authlm.connection_methods._oauth_helpers import PKCEPair

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(_network_error)
        ),
    )
    pair = PKCEPair(verifier="test-verifier", challenge="test-challenge")
    with pytest.raises(RefreshFailed, match="network error"):
        await method._exchange_code(  # type: ignore[reportPrivateUsage]  # noqa: SLF001
            code="test-code", pair=pair, redirect_uri="http://127.0.0.1:0/callback"
        )


@pytest.mark.asyncio
async def test_exchange_code_503_raises_refresh_failed() -> None:
    """_exchange_code() raises RefreshFailed on 503, not TokenEndpointError."""

    def _server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server_error"})

    from authlm.connection_methods._oauth_helpers import PKCEPair

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(_server_error)
        ),
    )
    pair = PKCEPair(verifier="test-verifier", challenge="test-challenge")
    with pytest.raises(RefreshFailed):
        await method._exchange_code(  # type: ignore[reportPrivateUsage]  # noqa: SLF001
            code="test-code", pair=pair, redirect_uri="http://127.0.0.1:0/callback"
        )
