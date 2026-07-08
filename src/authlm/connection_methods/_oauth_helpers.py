from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import HttpUrl

from authlm.credentials import OAuthCredential
from authlm.errors import TokenEndpointError

_log = logging.getLogger(__name__)

_REDACTED_PARAMS: frozenset[str] = frozenset(
    {
        "code",
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "client_secret",
        "api_key",
        "secret",
    }
)
_FATAL_ERROR_CODES: frozenset[str] = frozenset(
    {
        "invalid_grant",
        "expired_token",
        "expired_refresh_token",
        "revoked",
        "access_denied",
        "entitlement_denied",
    }
)
_ACCESS_DENIED_CODES: frozenset[str] = frozenset(
    {"entitlement_denied", "access_denied"}
)
_REDACTED_VALUE: str = "[REDACTED]"
_REDACT_DICT_KEYS: frozenset[str] = frozenset(
    {"access_token", "refresh_token", "code", "client_secret", "api_key", "secret"}
)
_BEARER_TOKEN_RE: re.Pattern[str] = re.compile(r"Bearer [A-Za-z0-9_-]{8,}")
_TOKEN_PARAM_RE: re.Pattern[str] = re.compile(
    r"\b(access_token|refresh_token|id_token|client_secret|api_key|secret|code)\b"
    r"\s*[\"']?\s*[=:]\s*[\"']?"
    r"(\"[^\"]*\"|[^\s,;&}]+)"
)


@dataclass(frozen=True)
class PKCEPair:
    """PKCE verifier/challenge pair using the S256 method."""

    verifier: str
    challenge: str


@dataclass(frozen=True)
class TokenError:
    """Classification of a token endpoint failure.

    ``fatal_reason`` is ``"access_denied"`` when the token works but the user
    lacks access (e.g. ``entitlement_denied``), ``"reconnection"`` when the
    refresh token is dead (e.g. ``invalid_grant``), and ``None`` for non-fatal
    errors.
    """

    status_code: int
    error_code: str
    fatal: bool
    fatal_reason: Literal["reconnection", "access_denied"] | None = None


def generate_pkce_pair() -> PKCEPair:
    """Generate a random PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return PKCEPair(verifier=verifier, challenge=challenge)


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


def redact_body(body: str) -> str:
    """Redact secrets in request/response bodies.

    Parses JSON bodies and redacts known secret keys. Falls back to
    regex-based redaction for non-JSON content. Truncates to 200 chars.
    """
    if not body:
        return body
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            _redact_dict(data)
            return json.dumps(data)
    except (json.JSONDecodeError, ValueError):
        pass
    redacted = _BEARER_TOKEN_RE.sub(f"Bearer {_REDACTED_VALUE}", body)
    redacted = _TOKEN_PARAM_RE.sub(rf"\1={_REDACTED_VALUE}", redacted)
    return redacted[:200]


def _redact_dict(data: dict[str, object]) -> None:
    """Recursively replace values of known secret keys with a redacted placeholder."""
    for key, value in data.items():
        if key in _REDACT_DICT_KEYS:
            data[key] = _REDACTED_VALUE
        elif isinstance(value, dict):
            _redact_dict(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _redact_dict(item)


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
    fatal_reason: Literal["reconnection", "access_denied"] | None = None
    if fatal:
        if error_code in _ACCESS_DENIED_CODES:
            fatal_reason = "access_denied"
        else:
            fatal_reason = "reconnection"
    return TokenError(
        status_code=status_code,
        error_code=error_code,
        fatal=fatal,
        fatal_reason=fatal_reason,
    )


def build_oauth_credential(
    *,
    data: dict[str, Any],
    provider: str,
    alias: str,
    method_id: str,
    client_id: str | None = None,
) -> OAuthCredential:
    """Parse a token-endpoint response into an OAuthCredential."""
    access_token = data.get("access_token")
    if not access_token:
        raise TokenEndpointError("token response missing access_token")
    raw_rt = data.get("refresh_token")
    refresh_token = str(raw_rt) if raw_rt is not None else None
    expires_in = data.get("expires_in")
    expires_at: datetime | None = None
    if isinstance(expires_in, (int, float)):
        expires_at = datetime.now(UTC) + timedelta(seconds=float(expires_in))
    raw_scopes = data.get("scope") or data.get("scopes")
    scopes: list[str] = []
    if isinstance(raw_scopes, str):
        scopes = raw_scopes.split()
    elif isinstance(raw_scopes, list):
        scopes = [str(s) for s in raw_scopes]
    return OAuthCredential(
        provider=provider,
        alias=alias,
        method_id=method_id,
        access_token=str(access_token),
        refresh_token=refresh_token,
        expires_at=expires_at,
        scopes=scopes,
        client_id=client_id,
    )
