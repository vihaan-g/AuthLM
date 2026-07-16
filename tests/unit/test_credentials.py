from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from authlm.credentials import (
    ApiKeyCredential,
    Credential,
    CredentialUnion,
    OAuthCredential,
    compute_fingerprint,
    parse_credential,
)


def _utc(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=UTC)


def test_credential_base_constructs() -> None:
    cred = Credential(provider="p", alias="a", method_id="m")
    assert cred.provider == "p"
    assert cred.alias == "a"
    assert cred.warning_acknowledged_at is None


def test_api_key_credential_fields() -> None:
    cred = ApiKeyCredential(
        provider="openai",
        alias="default",
        method_id="api_key",
        secret="sk-test",
    )
    assert cred.type == "api_key"
    assert cred.secret == "sk-test"
    assert cred.warning_acknowledged_at is None


def test_oauth_credential_fields() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="chatgpt_oauth_browser",
        access_token="access",
        refresh_token=None,
        expires_at=_utc(2030),
        scopes=["openid"],
        client_id="cid",
    )
    assert cred.type == "oauth"
    assert cred.scopes == ["openid"]
    assert cred.refresh_token is None


def test_oauth_scopes_default_empty() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="m",
        access_token="access",
        refresh_token=None,
        expires_at=None,
    )
    assert cred.scopes == []
    assert cred.client_id is None


_ADAPTER: TypeAdapter[CredentialUnion] = TypeAdapter(CredentialUnion)


def test_union_parses_api_key() -> None:
    cred = _ADAPTER.validate_python(
        {
            "type": "api_key",
            "provider": "openai",
            "alias": "default",
            "method_id": "api_key",
            "secret": "sk-test",
        }
    )
    assert isinstance(cred, ApiKeyCredential)


def test_union_parses_oauth() -> None:
    cred = _ADAPTER.validate_python(
        {
            "type": "oauth",
            "provider": "openai",
            "alias": "default",
            "method_id": "m",
            "access_token": "a",
            "refresh_token": None,
            "expires_at": None,
        }
    )
    assert isinstance(cred, OAuthCredential)


def test_union_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python(
            {"type": "unknown", "provider": "p", "alias": "a", "method_id": "m"}
        )


def test_parse_credential_api_key() -> None:
    cred = ApiKeyCredential(
        provider="openai",
        alias="default",
        method_id="api_key",
        secret="sk-test",
    )
    parsed = parse_credential(cred.model_dump_json())
    assert isinstance(parsed, ApiKeyCredential)
    assert parsed.secret == "sk-test"
    assert parsed.provider == "openai"


def test_parse_credential_oauth() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="m",
        access_token="a",
        refresh_token=None,
        expires_at=None,
    )
    parsed = parse_credential(cred.model_dump_json())
    assert isinstance(parsed, OAuthCredential)
    assert parsed.access_token == "a"


def test_parse_credential_bytes_input() -> None:
    cred = ApiKeyCredential(provider="p", alias="a", method_id="m", secret="s")
    parsed = parse_credential(cred.model_dump_json().encode())
    assert isinstance(parsed, ApiKeyCredential)


def test_compute_fingerprint_length() -> None:
    fp = compute_fingerprint("sk-test")
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_compute_fingerprint_deterministic() -> None:
    assert compute_fingerprint("sk-test") == compute_fingerprint("sk-test")


def test_compute_fingerprint_unique_per_secret() -> None:
    assert compute_fingerprint("sk-a") != compute_fingerprint("sk-b")


def test_compute_fingerprint_empty() -> None:
    fp = compute_fingerprint("")
    assert len(fp) == 16


def test_api_key_credential_repr_does_not_leak_secret() -> None:
    cred = ApiKeyCredential(
        provider="openai",
        alias="default",
        method_id="api_key",
        secret="sk-supersecret123",
    )
    repr_str = repr(cred)
    assert "sk-supersecret123" not in repr_str


def test_oauth_credential_repr_does_not_leak_tokens() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="ya29.secret-token",
        refresh_token="rt-refresh-secret",
        expires_at=None,
        scopes=["openid"],
    )
    repr_str = repr(cred)
    assert "ya29.secret-token" not in repr_str
    assert "rt-refresh-secret" not in repr_str
