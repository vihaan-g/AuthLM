from __future__ import annotations

import logging
import secrets
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import HttpUrl
from typing_extensions import override

from authlm.connection_methods._oauth_helpers import (
    PKCEPair,
    build_authorize_url,
    classify_token_error,
    exchange_code_for_token,
    generate_pkce_pair,
    redact_url,
)
from authlm.credentials import Credential, OAuthCredential
from authlm.errors import ReconnectionRequired, TokenEndpointError
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores.base import CredentialStore

_log = logging.getLogger(__name__)


class _LoopbackServer(Protocol):
    def serve_forever(self) -> None: ...
    def shutdown(self) -> None: ...
    def server_close(self) -> None: ...


def _default_loopback_factory(
    addr: tuple[str, int], handler: type[BaseHTTPRequestHandler]
) -> _LoopbackServer:
    class _ReuseAddrServer(HTTPServer):
        allow_reuse_address = True

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
        redirect_path: str = "/callback",
        loopback_factory: Callable[
            [tuple[str, int], type[BaseHTTPRequestHandler]], _LoopbackServer
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
        self._redirect_path = redirect_path
        self._loopback_factory = loopback_factory
        self._open_browser = open_browser
        self._http_client = http_client

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
    async def validate(self, cred: Credential, *, force: bool) -> bool:
        if not isinstance(cred, OAuthCredential):
            return False
        if cred.expires_at is None:
            return True
        if cred.expires_at.tzinfo is None:
            return cred.expires_at > datetime.now()
        return cred.expires_at > datetime.now(UTC)

    @override
    async def connect(self, *, store: CredentialStore) -> Credential:
        if self._http_client is None:
            raise RuntimeError("http_client is required for connect()")
        pair = generate_pkce_pair()
        state = secrets.token_urlsafe(24)
        redirect_uri = f"http://127.0.0.1:{self._redirect_port}{self._redirect_path}"

        captured: dict[str, str] = {}
        server = self._start_loopback(captured, state)

        try:
            authorize_url = build_authorize_url(
                authorize_url=self._authorize_url,
                client_id=self._client_id,
                redirect_uri=redirect_uri,
                scope=" ".join(self._scopes),
                state=state,
                code_challenge=pair.challenge,
            )
            _log.info("Opening browser to %s", redact_url(authorize_url))
            self._open_browser(authorize_url)
            code = self._wait_for_code(captured, timeout=300.0)
        finally:
            server.shutdown()
            server.server_close()

        return await self._exchange_code(
            code=code, pair=pair, redirect_uri=redirect_uri
        )

    def _start_loopback(
        self, captured: dict[str, str], expected_state: str
    ) -> _LoopbackServer:
        outer_self = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                query = parse_qs(urlparse(self.path).query)
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

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        server = outer_self._loopback_factory(
            ("127.0.0.1", outer_self._redirect_port), Handler
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def _wait_for_code(self, captured: dict[str, str], *, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if "code" in captured:
                return captured["code"]
            time.sleep(0.05)
        raise TimeoutError("OAuth PKCE flow timed out waiting for callback")

    async def _exchange_code(
        self, *, code: str, pair: PKCEPair, redirect_uri: str
    ) -> OAuthCredential:
        assert self._http_client is not None
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "code_verifier": pair.verifier,
        }
        response = await exchange_code_for_token(
            http_client=self._http_client,
            token_url=str(self._token_url),
            payload=payload,
        )
        classification = classify_token_error(
            status_code=response.status_code, body=response.text
        )
        if classification.fatal:
            code = classification.error_code or str(response.status_code)
            raise ReconnectionRequired(f"Token endpoint returned {code}")
        if not (200 <= response.status_code < 300):
            raise TokenEndpointError(
                f"Token endpoint error: status={response.status_code} "
                f"body={response.text[:300]}"
            )
        data = response.json()
        return self._build_credential(data)

    def _build_credential(self, data: dict[str, Any]) -> OAuthCredential:
        access = str(data.get("access_token", ""))
        if not access:
            raise TokenEndpointError("token response missing access_token")
        refresh = data.get("refresh_token")
        expires_in = data.get("expires_in")
        expires_at: datetime | None = None
        if isinstance(expires_in, (int, float)):
            expires_at = datetime.now(UTC) + timedelta(seconds=float(expires_in))
        scopes_field = data.get("scope") or data.get("scopes") or ""
        if isinstance(scopes_field, str):
            scopes = [s for s in scopes_field.split() if s]
        else:
            scopes = [str(s) for s in scopes_field]
        return OAuthCredential(
            provider=self._provider_id,
            alias="default",
            method_id=self.id,
            access_token=access,
            refresh_token=str(refresh) if refresh else None,
            expires_at=expires_at,
            scopes=scopes,
            client_id=self._client_id,
        )
