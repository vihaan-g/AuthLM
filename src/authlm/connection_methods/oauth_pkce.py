from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
import threading
import webbrowser
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import HttpUrl
from typing_extensions import override

from authlm.connection_methods._oauth_helpers import (
    PKCEPair,
    build_authorize_url,
    build_oauth_credential,
    classify_token_error,
    generate_pkce_pair,
    redact_body,
    redact_url,
)
from authlm.credentials import Credential, OAuthCredential
from authlm.errors import (
    AccessDenied,
    AuthLMError,
    ConnectionTimeout,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores.base import CredentialStore

_log = logging.getLogger(__name__)


def _default_loopback_factory(
    addr: tuple[str, int], handler: type[BaseHTTPRequestHandler]
) -> ThreadingHTTPServer:
    class _ReuseAddrServer(ThreadingHTTPServer):
        allow_reuse_address = sys.platform != "win32"

    return _ReuseAddrServer(addr, handler)


def _default_open_browser(url: str) -> None:
    webbrowser.open(url)


class OAuthPKCEMethod(ConnectionMethod):
    """PKCE browser flow with a loopback HTTP server to capture the auth code."""

    def __init__(
        self,
        *,
        provider_id: str,
        authorize_url: HttpUrl,
        token_url: HttpUrl,
        client_id: str,
        scopes: Sequence[str],
        redirect_port: int,
        fixed_redirect_uri: str | None = None,
        extra_authorize_params: dict[str, str] | None = None,
        loopback_factory: Callable[
            [tuple[str, int], type[BaseHTTPRequestHandler]], ThreadingHTTPServer
        ] = _default_loopback_factory,
        open_browser: Callable[[str], None] = _default_open_browser,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._authorize_url = authorize_url
        self._token_url = token_url
        self._client_id = client_id
        self._scopes: tuple[str, ...] = tuple(scopes)
        self._redirect_port = redirect_port
        self._fixed_redirect_uri = fixed_redirect_uri
        self._extra_authorize_params = extra_authorize_params or {}
        self._redirect_path = "/callback"

        if fixed_redirect_uri is not None:
            parsed_redirect_uri = urlparse(fixed_redirect_uri)
            if parsed_redirect_uri.port is None or not parsed_redirect_uri.path:
                raise ValueError("fixed_redirect_uri must include a port and path")
            self._redirect_port = parsed_redirect_uri.port
            self._redirect_path = parsed_redirect_uri.path
        else:
            override = os.environ.get("AUTHLM_PKCE_PORT_OVERRIDE")
            if override is not None:
                try:
                    self._redirect_port = int(override)
                except ValueError:
                    _log.warning(
                        "AUTHLM_PKCE_PORT_OVERRIDE=%r is not a valid port number; "
                        "using default %d",
                        override,
                        redirect_port,
                    )
        self._loopback_factory = loopback_factory
        self._open_browser = open_browser
        self._http_client = http_client

    def with_open_browser(self, callback: Callable[[str], None]) -> OAuthPKCEMethod:
        """Return a new instance with the given open_browser callback.

        Mirrors ``APIKeyMethod.with_secret_prompt``; the CLI uses this
        to inject a Click-aware opener (e.g. one that logs the URL to
        stderr before invoking ``webbrowser.open``).
        """
        return OAuthPKCEMethod(
            provider_id=self._provider_id,
            authorize_url=self._authorize_url,
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            redirect_port=self._redirect_port,
            fixed_redirect_uri=self._fixed_redirect_uri,
            extra_authorize_params=self._extra_authorize_params,
            loopback_factory=self._loopback_factory,
            open_browser=callback,
            http_client=self._http_client,
        )

    @property
    @override
    def id(self) -> str:
        return "oauth_browser"

    @property
    @override
    def label(self) -> str:
        return "Browser OAuth (PKCE)"

    @property
    @override
    def warning(self) -> str | None:
        return None

    @property
    @override
    def oauth_grant(self) -> OAuthGrant | None:
        return OAuthGrant.AUTHORIZATION_CODE_PKCE

    @override
    async def connect(self, *, store: CredentialStore) -> Credential:
        pair = generate_pkce_pair()
        state = secrets.token_urlsafe(24)

        captured: dict[str, str] = {}
        server = self._start_loopback(captured, state)
        # Build redirect_uri after _start_loopback so it reflects any
        # port reassignment from port fallback (H1).
        redirect_uri = self._fixed_redirect_uri or (
            f"http://127.0.0.1:{self._redirect_port}{self._redirect_path}"
        )

        try:
            authorize_url = build_authorize_url(
                authorize_url=self._authorize_url,
                client_id=self._client_id,
                redirect_uri=redirect_uri,
                scope=" ".join(self._scopes),
                state=state,
                code_challenge=pair.challenge,
                extra_params=self._extra_authorize_params or None,
            )
            _log.debug("Opening browser to %s", redact_url(authorize_url))
            self._open_browser(authorize_url)
            code = await self._wait_for_code(captured, timeout=300.0)
        finally:
            server.shutdown()
            server.server_close()

        if self._http_client is not None:
            return await self._exchange_code(
                code=code,
                pair=pair,
                redirect_uri=redirect_uri,
                client=self._http_client,
            )
        async with httpx.AsyncClient() as client:
            return await self._exchange_code(
                code=code,
                pair=pair,
                redirect_uri=redirect_uri,
                client=client,
            )

    def _start_loopback(
        self, captured: dict[str, str], expected_state: str
    ) -> ThreadingHTTPServer:
        loop = asyncio.get_event_loop()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                query = parse_qs(urlparse(self.path).query)
                received_error = query.get("error", [""])[0]
                if received_error:
                    captured["error"] = received_error
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body>Authorization denied."
                        b" You may close this tab.</body></html>"
                    )
                    event = captured.get("_event")
                    if isinstance(event, asyncio.Event):
                        loop.call_soon_threadsafe(event.set)
                    return
                if "code" in captured:
                    self.send_response(410)
                    self.end_headers()
                    self.wfile.write(b"already handled")
                    return
                received_state = query.get("state", [""])[0]
                if received_state != expected_state:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"state mismatch")
                    return
                captured["code"] = query.get("code", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body>Authorized. You may close this tab.</body></html>"
                )
                event = captured.get("_event")
                if isinstance(event, asyncio.Event):
                    loop.call_soon_threadsafe(event.set)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        try:
            server = self._loopback_factory(("127.0.0.1", self._redirect_port), Handler)
        except OSError as exc:
            if self._fixed_redirect_uri is not None:
                raise AuthLMError(
                    f"Port {self._redirect_port} is required by fixed redirect URI "
                    f"{self._fixed_redirect_uri}. Free the port and try again."
                ) from exc
            try:
                server = self._loopback_factory(("127.0.0.1", 0), Handler)
                self._redirect_port = server.server_address[1]
            except OSError as exc:
                raise AuthLMError(
                    f"Port {self._redirect_port} is in use and no "
                    f"random port is available. Free a port or set "
                    f"AUTHLM_PKCE_PORT_OVERRIDE."
                ) from exc

        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    async def _wait_for_code(self, captured: dict[str, str], *, timeout: float) -> str:
        event = asyncio.Event()
        captured["_event"] = event  # type: ignore[assignment]

        if "code" in captured:
            return captured["code"]
        if captured.get("error") == "oauth_state_mismatch":
            raise AuthLMError(
                "OAuth state mismatch — the callback state parameter "
                "did not match the expected value. This may indicate a "
                "CSRF attack, a misconfigured redirect URI, or a "
                "browser/tool that modified the callback URL."
            )
        if "error" in captured:
            raise TokenEndpointError(
                f"Authorization denied by user for {self._provider_id}: "
                f"{captured['error']}"
            )

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            raise ConnectionTimeout(
                "OAuth PKCE flow timed out waiting for callback"
            ) from None
        finally:
            captured.pop("_event", None)

        if "error" in captured:
            raise TokenEndpointError(
                f"Authorization denied by user for {self._provider_id}: "
                f"{captured['error']}"
            )

        return captured["code"]

    async def _exchange_code(
        self,
        *,
        code: str,
        pair: PKCEPair,
        redirect_uri: str,
        client: httpx.AsyncClient | None = None,
    ) -> OAuthCredential:
        http_client = client or self._http_client
        if http_client is None:
            raise RuntimeError("http_client is required for _exchange_code")
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "code_verifier": pair.verifier,
        }
        _log.debug("POST %s", redact_url(str(self._token_url)))
        try:
            response = await http_client.post(
                str(self._token_url), data=payload, timeout=30.0
            )
        except httpx.HTTPError as exc:
            raise RefreshFailed(
                f"Token exchange network error for {self._provider_id}: "
                f"POST {redact_url(str(self._token_url))}"
            ) from exc
        classification = classify_token_error(
            status_code=response.status_code, body=response.text
        )
        if classification.fatal:
            if classification.fatal_reason == "access_denied":
                raise AccessDenied(
                    f"Token exchange error for {self._provider_id}: "
                    f"{classification.error_code}"
                )
            code = classification.error_code or str(response.status_code)
            raise ReconnectionRequired(f"Token endpoint returned {code}")
        if 500 <= response.status_code < 600:
            raise RefreshFailed(
                f"Token exchange server error for {self._provider_id}: "
                f"HTTP {response.status_code}"
            )
        if not (200 <= response.status_code < 300):
            raise TokenEndpointError(
                f"Token endpoint error: status={response.status_code} "
                f"body={redact_body(response.text)}"
            )
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise TokenEndpointError(
                f"Token endpoint returned non-JSON body: "
                f"body={redact_body(response.text)}"
            ) from exc
        return build_oauth_credential(
            data=data,
            provider=self._provider_id,
            alias="default",
            method_id=self.id,
            client_id=self._client_id,
        )
