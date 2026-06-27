from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from respx import MockRouter

from authlm.api import (
    connect,
    get_credential,
    get_valid_credential,
    refresh,
    should_refresh,
    validate,
)
from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.errors import CredentialNotFound, ReconnectionRequired
from authlm.providers.registry import get_method
from authlm.stores import MemoryStore


def _utc_future(hours: float = 1.0) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def _utc_past(minutes: float = 1.0) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


def test_should_refresh_false_for_api_key() -> None:
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk"
    )
    assert should_refresh(cred, margin=timedelta(minutes=5)) is False


def test_should_refresh_true_for_expired() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="a",
        refresh_token="r",
        expires_at=_utc_past(1.0),
    )
    assert should_refresh(cred, margin=timedelta(minutes=5)) is True


def test_should_refresh_true_within_margin() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    assert should_refresh(cred, margin=timedelta(minutes=5)) is True


def test_should_refresh_false_for_no_expiry() -> None:
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="a",
        refresh_token="r",
        expires_at=None,
    )
    assert should_refresh(cred, margin=timedelta(minutes=5)) is False


@pytest.mark.asyncio
async def test_get_credential_returns_stored() -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk"
        )
    )
    cred = await get_credential("openai", alias="default", store=store)
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk"


@pytest.mark.asyncio
async def test_get_credential_missing_raises() -> None:
    with pytest.raises(CredentialNotFound):
        await get_credential("openai", alias="default", store=MemoryStore())


@pytest.mark.asyncio
async def test_get_valid_credential_skips_refresh_when_fresh() -> None:
    store = MemoryStore()
    store.set(
        OAuthCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            access_token="a",
            refresh_token="r",
            expires_at=_utc_future(1.0),
        )
    )
    out = await get_valid_credential(
        "openai", alias="default", margin=timedelta(minutes=5), store=store
    )
    assert isinstance(out, OAuthCredential)
    assert out.access_token == "a"


@pytest.mark.asyncio
async def test_get_valid_credential_refreshes_when_expired(
    respx_mock: MockRouter,
) -> None:
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        200,
        json={
            "access_token": "NEW",
            "refresh_token": "NEW_REFRESH",
            "expires_in": 3600,
            "scope": "openid",
        },
    )
    store = MemoryStore()
    store.set(
        OAuthCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            access_token="OLD",
            refresh_token="OLD_REFRESH",
            expires_at=_utc_past(1.0),
        )
    )
    out = await get_valid_credential(
        "openai", alias="default", margin=timedelta(minutes=5), store=store
    )
    assert isinstance(out, OAuthCredential)
    assert out.access_token == "NEW"
    stored = store.get("openai", "default")
    assert isinstance(stored, OAuthCredential)
    assert stored.access_token == "NEW"
    assert stored.refresh_token == "NEW_REFRESH"


@pytest.mark.asyncio
async def test_refresh_invalid_grant_raises_reconnection_required(
    respx_mock: MockRouter,
) -> None:
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        400, json={"error": "invalid_grant"}
    )
    store = MemoryStore()
    store.set(
        OAuthCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            access_token="a",
            refresh_token="r",
            expires_at=None,
        )
    )
    with pytest.raises(ReconnectionRequired):
        await refresh("openai", alias="default", store=store)


@pytest.mark.asyncio
async def test_connect_stores_credential() -> None:
    store = MemoryStore()
    method = get_method("openrouter", "api_key")
    cred = await connect(
        "openrouter",
        alias="default",
        store=store,
        method=method,
        secret_prompt=lambda _p: "sk-or-test",
    )
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-or-test"
    stored = store.get("openrouter", "default")
    assert stored is not None
    assert isinstance(stored, ApiKeyCredential)


@pytest.mark.asyncio
async def test_validate_delegates_to_validation_module(
    respx_mock: MockRouter,
) -> None:
    respx_mock.get("https://api.openai.com/v1/models").respond(
        200, json={"data": [{"id": "gpt-4o"}]}
    )
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    assert await validate(cred, force=False) is True
