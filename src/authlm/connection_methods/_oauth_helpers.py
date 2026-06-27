from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from pydantic import HttpUrl

_log = logging.getLogger(__name__)

_REDACTED_PARAMS: frozenset[str] = frozenset(
    {"code", "access_token", "refresh_token", "id_token", "token", "client_secret"}
)
_FATAL_ERROR_CODES: frozenset[str] = frozenset(
    {"invalid_grant", "expired_token", "expired_refresh_token", "revoked"}
)
_REDACTED_VALUE: str = "[REDACTED]"


@dataclass(frozen=True)
class PKCEPair:
    """PKCE verifier/challenge pair using the S256 method."""

    verifier: str
    challenge: str
    method: str


@dataclass(frozen=True)
class TokenError:
    """Classification of a token endpoint failure."""

    status_code: int
    error_code: str
    fatal: bool


def generate_pkce_pair() -> PKCEPair:
    """Generate a random PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return PKCEPair(verifier=verifier, challenge=challenge, method="S256")


def build_authorize_url(
    *,
    authorize_url: HttpUrl,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
) -> str:
    """Build an OAuth 2.0 authorization URL with PKCE parameters."""
    parsed = urlparse(str(authorize_url))
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    oauth_params: list[tuple[str, str]] = [
        ("response_type", "code"),
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("scope", scope),
        ("state", state),
        ("code_challenge", code_challenge),
        ("code_challenge_method", "S256"),
    ]
    merged = existing + oauth_params
    return urlunparse(parsed._replace(query=urlencode(merged)))


def redact_url(url: str) -> str:
    """Return ``url`` with sensitive query parameters replaced by ``[REDACTED]``."""
    parsed = urlparse(url)
    redacted_pairs: list[tuple[str, str]] = [
        (key, _REDACTED_VALUE if key in _REDACTED_PARAMS else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(redacted_pairs)))


def classify_token_error(*, status_code: int, body: str) -> TokenError:
    """Classify a token endpoint error response.

    Returns a :class:`TokenError` with ``fatal=True`` only for refresh-token
    revocation conditions that require re-authentication. Network failures
    (status 0) and 5xx server errors are non-fatal (retryable). Other 4xx
    errors with a non-fatal OAuth error code are non-fatal.
    """
    error_code: str = ""
    try:
        parsed_body: object = json.loads(body)
    except (ValueError, TypeError):
        parsed_body = None
    if isinstance(parsed_body, dict):
        raw_error: object = parsed_body.get("error")
        if isinstance(raw_error, str):
            error_code = raw_error

    if status_code >= 500 or status_code == 0:
        return TokenError(status_code=status_code, error_code=error_code, fatal=False)

    fatal = error_code in _FATAL_ERROR_CODES
    return TokenError(status_code=status_code, error_code=error_code, fatal=fatal)


async def exchange_code_for_token(
    *,
    http_client: httpx.AsyncClient,
    token_url: str,
    payload: dict[str, str],
) -> httpx.Response:
    """POST a token-endpoint form payload and return the raw response."""
    _log.debug("POST %s", redact_url(token_url))
    return await http_client.post(token_url, data=payload)
