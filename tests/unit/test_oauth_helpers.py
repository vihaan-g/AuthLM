from __future__ import annotations

import base64
import hashlib

import httpx
import pytest
from pydantic import HttpUrl

from authlm.connection_methods._oauth_helpers import (
    PKCEPair,
    TokenError,
    build_authorize_url,
    build_oauth_credential,
    classify_token_error,
    generate_pkce_pair,
    redact_body,
    redact_url,
)
from authlm.errors import TokenEndpointError


def test_generate_pkce_pair_returns_s256_pair() -> None:
    pair = generate_pkce_pair()

    assert isinstance(pair, PKCEPair)
    assert 43 <= len(pair.verifier) <= 128
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(pair.verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert pair.challenge == expected


def test_generate_pkce_pair_verifiers_are_unique() -> None:
    a = generate_pkce_pair()
    b = generate_pkce_pair()

    assert a.verifier != b.verifier


def test_build_authorize_url_includes_oauth_params() -> None:
    url = build_authorize_url(
        authorize_url=HttpUrl("https://provider.test/oauth/authorize"),
        client_id="client-123",
        redirect_uri="http://127.0.0.1:8765/callback",
        scope="openid profile",
        state="state-token",
        code_challenge="challenge-abc",
    )

    parsed = httpx.URL(url)
    params = dict(parsed.params)
    assert params["response_type"] == "code"
    assert params["client_id"] == "client-123"
    assert params["redirect_uri"] == "http://127.0.0.1:8765/callback"
    assert params["scope"] == "openid profile"
    assert params["state"] == "state-token"
    assert params["code_challenge"] == "challenge-abc"
    assert params["code_challenge_method"] == "S256"


def test_build_authorize_url_preserves_existing_query() -> None:
    url = build_authorize_url(
        authorize_url=HttpUrl("https://provider.test/oauth/authorize?foo=bar&baz=qux"),
        client_id="client-123",
        redirect_uri="http://127.0.0.1:8765/callback",
        scope="openid",
        state="state-token",
        code_challenge="challenge-abc",
    )

    parsed = httpx.URL(url)
    params = dict(parsed.params)
    assert params["foo"] == "bar"
    assert params["baz"] == "qux"
    assert params["client_id"] == "client-123"
    assert params["code_challenge"] == "challenge-abc"


def test_redact_url_redacts_code_preserves_state() -> None:
    redacted = redact_url("https://provider.test/cb?code=secret&state=abc")

    assert "secret" not in redacted
    assert "code=%5BREDACTED%5D" in redacted
    assert "state=abc" in redacted


def test_redact_url_redacts_other_sensitive_params() -> None:
    url = (
        "https://provider.test/cb"
        "?access_token=at-secret-xyz&refresh_token=rt-secret-xyz"
        "&id_token=it-secret-xyz&token=tk-secret-xyz"
        "&client_secret=cs-secret-xyz&safe=keepme"
    )

    redacted = redact_url(url)

    for secret in (
        "at-secret-xyz",
        "rt-secret-xyz",
        "it-secret-xyz",
        "tk-secret-xyz",
        "cs-secret-xyz",
    ):
        assert secret not in redacted
    assert "access_token=%5BREDACTED%5D" in redacted
    assert "refresh_token=%5BREDACTED%5D" in redacted
    assert "id_token=%5BREDACTED%5D" in redacted
    assert "token=%5BREDACTED%5D" in redacted
    assert "client_secret=%5BREDACTED%5D" in redacted
    assert "safe=keepme" in redacted


def test_redact_url_preserves_host() -> None:
    redacted = redact_url("https://provider.test/path?code=secret&state=abc")

    parsed = httpx.URL(redacted)
    assert parsed.host == "provider.test"
    assert parsed.path == "/path"


def test_classify_token_error_invalid_grant_fatal() -> None:
    result = classify_token_error(status_code=400, body='{"error":"invalid_grant"}')

    assert isinstance(result, TokenError)
    assert result.status_code == 400
    assert result.error_code == "invalid_grant"
    assert result.fatal is True


def test_classify_token_error_5xx_nonfatal() -> None:
    result = classify_token_error(status_code=503, body="Service Unavailable")

    assert result.status_code == 503
    assert result.fatal is False


def test_classify_token_error_status_zero_nonfatal() -> None:
    result = classify_token_error(status_code=0, body="connection refused")

    assert result.status_code == 0
    assert result.fatal is False


def test_classify_token_error_invalid_request_nonfatal() -> None:
    result = classify_token_error(status_code=400, body='{"error":"invalid_request"}')

    assert result.status_code == 400
    assert result.error_code == "invalid_request"
    assert result.fatal is False


def test_classify_token_error_entitlement_denied_fatal() -> None:
    result = classify_token_error(
        status_code=400, body='{"error":"entitlement_denied"}'
    )

    assert result.status_code == 400
    assert result.error_code == "entitlement_denied"
    assert result.fatal is True


def test_classify_token_error_entitlement_denied_is_access_denied() -> None:
    """entitlement_denied → fatal_reason='access_denied' per spec §5.3."""
    result = classify_token_error(
        status_code=400, body='{"error":"entitlement_denied"}'
    )

    assert result.fatal is True
    assert result.fatal_reason == "access_denied"


def test_classify_token_error_invalid_grant_is_reconnection() -> None:
    """invalid_grant → fatal_reason='reconnection' per spec §5.3."""
    result = classify_token_error(status_code=400, body='{"error":"invalid_grant"}')

    assert result.fatal is True
    assert result.fatal_reason == "reconnection"


def test_classify_token_error_non_fatal_has_no_reason() -> None:
    """Non-fatal errors should have fatal_reason=None."""
    result = classify_token_error(status_code=400, body='{"error":"invalid_request"}')
    assert result.fatal is False
    assert result.fatal_reason is None


def test_classify_token_error_5xx_nonfatal_has_no_reason() -> None:
    """5xx non-fatal errors should have fatal_reason=None."""
    result = classify_token_error(status_code=503, body="Service Unavailable")

    assert result.fatal is False
    assert result.fatal_reason is None


def test_redact_body_short_bearer_token() -> None:
    result = redact_body("error: Bearer abcdefgh for request")
    assert "abcdefgh" not in result
    assert "Bearer [REDACTED]" in result


def test_redact_body_redacts_code_param() -> None:
    result = redact_body('{"error":"invalid_grant","code":"auth-code-123"}')
    assert "auth-code-123" not in result
    assert "[REDACTED]" in result


def test_redact_body_redacts_api_key() -> None:
    result = redact_body('{"api_key": "sk-secret123", "other": "ok"}')
    assert "sk-secret123" not in result
    assert "[REDACTED]" in result


def test_redact_body_redacts_secret() -> None:
    result = redact_body('{"secret": "my-secret-value", "other": "ok"}')
    assert "my-secret-value" not in result
    assert "[REDACTED]" in result


def test_build_oauth_credential_parses_token_response() -> None:
    data = {
        "access_token": "at-test",
        "refresh_token": "rt-test",
        "expires_in": 3600,
        "scope": "openid profile",
    }
    cred = build_oauth_credential(
        data=data,
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        client_id="test-client",
    )
    assert cred.access_token == "at-test"
    assert cred.refresh_token == "rt-test"
    assert cred.scopes == ["openid", "profile"]
    assert cred.client_id == "test-client"
    assert cred.expires_at is not None


def test_build_oauth_credential_handles_missing_refresh_token() -> None:
    data = {"access_token": "at-test", "expires_in": 3600}
    cred = build_oauth_credential(
        data=data, provider="openai", alias="default", method_id="oauth_browser"
    )
    assert cred.refresh_token is None


def test_build_oauth_credential_handles_scopes_as_list() -> None:
    data = {"access_token": "at-test", "scopes": ["openid", "email"]}
    cred = build_oauth_credential(
        data=data, provider="openai", alias="default", method_id="oauth_browser"
    )
    assert cred.scopes == ["openid", "email"]


def test_redact_body_recursive_nested_secrets() -> None:
    result = redact_body(
        '{"error":"invalid_grant","details":{"access_token":"abc123","extra":"keep"}}'
    )
    assert "abc123" not in result
    assert "[REDACTED]" in result


def test_redact_body_recursive_lists_of_dicts() -> None:
    result = redact_body(
        '{"errors":[{"access_token":"at1"},{"refresh_token":"rt1","other":"ok"}]}'
    )
    assert "at1" not in result
    assert "rt1" not in result
    assert "[REDACTED]" in result
    assert "other" in result
    assert "ok" in result


def test_build_oauth_credential_raises_on_missing_access_token() -> None:
    data = {"expires_in": 3600}
    with pytest.raises(TokenEndpointError):
        build_oauth_credential(
            data=data, provider="openai", alias="default", method_id="test"
        )
