from __future__ import annotations

import asyncio
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def _make_callback_trigger(port: int, code: str) -> Callable[[str], None]:
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
async def test_connect_uses_fixed_redirect_uri(respx_mock: MockRouter) -> None:
    port = 14559
    expected_redirect_uri = f"http://localhost:{port}/auth/callback"
    token_route = respx_mock.post("https://auth.openai.com/oauth/token").respond(
        200, json=_token_response()
    )

    def open_browser(authorize_url: str) -> None:
        query = parse_qs(urlparse(authorize_url).query)
        assert query["redirect_uri"] == [expected_redirect_uri]
        state = query["state"][0]
        urlopen(
            f"http://127.0.0.1:{port}/auth/callback?code=AUTHCODE&state={state}"
        ).read()

    async with httpx.AsyncClient() as client:
        method = OAuthPKCEMethod(
            provider_id="openai",
            authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
            token_url=HttpUrl("https://auth.openai.com/oauth/token"),
            client_id="test-client",
            scopes=("openid", "profile"),
            redirect_port=port,
            fixed_redirect_uri=expected_redirect_uri,
            http_client=client,
            open_browser=open_browser,
        )
        await method.connect(store=MemoryStore())

    request_body = token_route.calls.last.request.content.decode()
    expected_escaped_uri = f"http%3A%2F%2Flocalhost%3A{port}%2Fauth%2Fcallback"
    assert f"redirect_uri={expected_escaped_uri}" in request_body


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
    server = method._start_loopback(captured, "expected-state")  # noqa: SLF001
    port = server.server_address[1]
    try:
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"http://127.0.0.1:{port}/callback?state=wrong&code=testcode")
        assert exc_info.value.code == 400
        assert "code" not in captured
        assert "error" not in captured
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
    server = method._start_loopback(captured, "expected-state")  # noqa: SLF001
    port = server.server_address[1]
    try:
        response = urlopen(
            f"http://127.0.0.1:{port}/callback?error=access_denied&state=expected-state"
        )
        assert response.status == 200
        body = response.read().decode()
        assert "denied" in body.lower()
        assert "code" not in captured
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_handler_denial_unblocks_wait_for_code_immediately() -> None:
    """Callback with error parameter unblocks wait for code immediately."""
    async with httpx.AsyncClient() as client:

        def open_browser_with_denial(authorize_url: str) -> None:
            query = parse_qs(urlparse(authorize_url).query)
            state = query.get("state", [""])[0]
            parsed_redirect = urlparse(query.get("redirect_uri", [""])[0])
            port = parsed_redirect.port or 14557
            urlopen(
                f"http://127.0.0.1:{port}/callback?error=access_denied&state={state}"
            ).read()

        method = OAuthPKCEMethod(
            provider_id="openai",
            authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
            token_url=HttpUrl("https://auth.openai.com/oauth/token"),
            client_id="test-client",
            scopes=("openid", "profile"),
            redirect_port=14557,
            http_client=client,
            open_browser=open_browser_with_denial,
        )
        with pytest.raises(TokenEndpointError, match="Authorization denied"):
            await method.connect(store=MemoryStore())


@pytest.mark.asyncio
async def test_port_collision_raises_authlm_error() -> None:
    """When the loopback factory raises OSError, raise AuthLMError."""

    def _failing_factory(
        addr: tuple[str, int], handler: type[BaseHTTPRequestHandler]
    ) -> ThreadingHTTPServer:
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
        method._start_loopback({}, "state")  # noqa: SLF001


@pytest.mark.asyncio
async def test_port_fallback_to_zero_on_collision() -> None:
    """When preferred port is occupied, fall back to port=0."""

    class FakeServer:
        def __init__(self, addr: tuple[str, int], handler: Any) -> None:
            self.server_address: tuple[str, int] = (
                addr[0],
                9999 if addr[1] == 0 else addr[1],
            )

        def serve_forever(self) -> None:
            pass

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    call_count = 0

    def factory(
        addr: tuple[str, int], handler: type[BaseHTTPRequestHandler]
    ) -> ThreadingHTTPServer:
        nonlocal call_count
        call_count += 1
        if call_count == 1 and addr[1] != 0:
            raise OSError("Address already in use")
        return FakeServer(addr, handler)  # type: ignore[return-value]

    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=1455,
        loopback_factory=factory,
    )
    method._start_loopback({}, "state")  # noqa: SLF001
    assert method._redirect_port == 9999  # noqa: SLF001
    assert call_count == 2


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
        await method._wait_for_code(captured, timeout=0.01)  # noqa: SLF001


@pytest.mark.asyncio
async def test_state_mismatch_raises_authlm_error_not_timeout() -> None:
    """State mismatch should raise AuthLMError with useful message."""
    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
    )
    captured: dict[str, str] = {"error": "oauth_state_mismatch"}
    with pytest.raises(AuthLMError, match="state mismatch"):
        await method._wait_for_code(captured, timeout=0.01)  # noqa: SLF001


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
        await method._exchange_code(  # noqa: SLF001
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
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_network_error)),
    )
    pair = PKCEPair(verifier="test-verifier", challenge="test-challenge")
    with pytest.raises(RefreshFailed, match="network error"):
        await method._exchange_code(  # noqa: SLF001
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
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_server_error)),
    )
    pair = PKCEPair(verifier="test-verifier", challenge="test-challenge")
    with pytest.raises(RefreshFailed):
        await method._exchange_code(  # noqa: SLF001
            code="test-code", pair=pair, redirect_uri="http://127.0.0.1:0/callback"
        )


@pytest.mark.asyncio
async def test_wait_for_code_registers_event_before_check() -> None:
    method = OAuthPKCEMethod(
        provider_id="test",
        authorize_url=HttpUrl("https://example.com/auth"),
        token_url=HttpUrl("https://example.com/token"),
        client_id="test",
        scopes=["openid"],
        redirect_port=0,
    )
    captured: dict[str, Any] = {}

    # Start wait_for_code in background task
    task = asyncio.create_task(method._wait_for_code(captured, timeout=1.0))  # type: ignore[arg-type]
    await asyncio.sleep(0.01)

    assert "_event" in captured
    assert isinstance(captured["_event"], asyncio.Event)

    # Trigger event
    captured["code"] = "valid-code"
    captured["_event"].set()

    code = await task
    assert code == "valid-code"
