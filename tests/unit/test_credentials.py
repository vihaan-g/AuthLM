from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from authlm.credentials import (
    ApiKeyCredential,
    AwsCredential,
    AzureAdCredential,
    Credential,
    CredentialUnion,
    OAuthCredential,
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


def test_aws_credential_fields() -> None:
    cred = AwsCredential(
        provider="aws",
        alias="default",
        method_id="aws",
        access_key_id="AKIA",
        secret_access_key="secret",
        session_token=None,
    )
    assert cred.type == "aws"
    assert cred.session_token is None


def test_azure_ad_credential_fields() -> None:
    cred = AzureAdCredential(
        provider="azure",
        alias="default",
        method_id="azure_ad",
        tenant_id="tid",
        client_id="cid",
        client_secret=None,
    )
    assert cred.type == "azure_ad"
    assert cred.access_token is None
    assert cred.expires_at is None


_ADAPTER = TypeAdapter(CredentialUnion)


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
