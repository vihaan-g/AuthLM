from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import HttpUrl
from respx import MockRouter

from authlm.api import (
    connect,
    get_credential,
    get_valid_credential,
    refresh,
    should_refresh,
)
from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.credentials import ApiKeyCredential, Credential, OAuthCredential
from authlm.errors import (
    AccessDenied,
    CredentialNotFound,
    ReconnectionRequired,
    RefreshFailed,
    SecretStoreError,
)
from authlm.metadata import MetadataStore
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
    from authlm.validation import validate as _validate

    respx_mock.get("https://api.openai.com/v1/models").respond(
        200, json={"data": [{"id": "gpt-4o"}]}
    )
    cred = ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )
    assert await _validate(cred, force=False) is True


@pytest.mark.asyncio
async def test_connect_propagates_on_prompt_to_device_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """api.connect(on_prompt=...) calls OAuthDeviceCodeMethod.with_on_prompt()."""
    method = OAuthDeviceCodeMethod(
        provider_id="openai",
        device_code_url=HttpUrl(
            "https://auth.openai.com/api/accounts/deviceauth/usercode"
        ),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="cid",
        scopes=("openid",),
        http_client=httpx.AsyncClient(),
    )

    captured: list[Callable[[str, str], None]] = []

    def stub_with_on_prompt(
        callback: Callable[[str, str], None],
    ) -> OAuthDeviceCodeMethod:
        captured.append(callback)
        return method

    monkeypatch.setattr(method, "with_on_prompt", stub_with_on_prompt)

    async def fake_connect(*, store: Any) -> ApiKeyCredential:
        return ApiKeyCredential(
            provider="openai",
            alias="default",
            method_id="oauth_device",
            secret="",
        )

    monkeypatch.setattr(method, "connect", fake_connect)

    def my_prompt(uri: str, code: str) -> None:
        pass

    await connect(
        "openai",
        alias="default",
        method=method,
        store=MemoryStore(),
        secret_prompt=lambda _: "",
        on_prompt=my_prompt,
    )
    assert captured == [my_prompt]


@pytest.mark.asyncio
async def test_connect_propagates_open_browser_to_pkce_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """api.connect(open_browser=...) calls OAuthPKCEMethod.with_open_browser()."""
    method = OAuthPKCEMethod(
        provider_id="openai",
        authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
        token_url=HttpUrl("https://auth.openai.com/oauth/token"),
        client_id="cid",
        scopes=("openid",),
        redirect_port=14999,
        http_client=httpx.AsyncClient(),
    )

    captured: list[Callable[[str], None]] = []

    def stub_with_open_browser(
        callback: Callable[[str], None],
    ) -> OAuthPKCEMethod:
        captured.append(callback)
        return method

    monkeypatch.setattr(method, "with_open_browser", stub_with_open_browser)

    async def fake_connect(*, store: Any) -> ApiKeyCredential:
        return ApiKeyCredential(
            provider="openai",
            alias="default",
            method_id="oauth_browser",
            secret="",
        )

    monkeypatch.setattr(method, "connect", fake_connect)

    def my_open(url: str) -> None:
        pass

    await connect(
        "openai",
        alias="default",
        method=method,
        store=MemoryStore(),
        secret_prompt=lambda _: "",
        open_browser=my_open,
    )
    assert captured == [my_open]


@pytest.mark.asyncio
async def test_refresh_keeps_old_refresh_token_when_server_omits_it() -> None:
    old_refresh = "rt-old-token"
    store = MemoryStore()
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="at-old",
        refresh_token=old_refresh,
        expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    store.set(cred)

    with respx.mock:
        respx.post(
            "https://auth.openai.com/oauth/token",
        ).respond(
            200,
            json={"access_token": "at-new", "expires_in": 3600},
        )

        result = await refresh("openai", alias="default", store=store)

    assert result.access_token == "at-new"
    assert result.refresh_token == old_refresh


@pytest.mark.asyncio
async def test_refresh_raises_reconnection_required_when_no_refresh_token() -> None:
    store = MemoryStore()
    cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="at-expired",
        refresh_token=None,
        expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    store.set(cred)

    with pytest.raises(ReconnectionRequired):
        await refresh("openai", alias="default", store=store)


@pytest.mark.asyncio
async def test_refresh_sets_expires_at_none_when_expires_in_absent() -> None:
    """When token endpoint omits expires_in, expires_at is None (not stale)."""
    store = MemoryStore()
    old_cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="at-old",
        refresh_token="rt-old",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    store.set(old_cred)

    with respx.mock:
        respx.post("https://auth.openai.com/oauth/token").respond(
            200,
            json={"access_token": "at-new", "refresh_token": "rt-new"},
            # no expires_in
        )
        result = await refresh("openai", alias="default", store=store)

    assert result.access_token == "at-new"
    assert result.expires_at is None  # not the old stale value


@pytest.mark.asyncio
async def test_get_credential_returns_expired_oauth_as_is() -> None:
    """get_credential returns expired OAuthCredential without refreshing."""
    store = MemoryStore()
    expired_cred = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="oauth_browser",
        access_token="at-expired",
        refresh_token="rt-valid",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        scopes=["openid"],
    )
    store.set(expired_cred)

    result = await get_credential("openai", alias="default", store=store)

    assert isinstance(result, OAuthCredential)
    assert result.access_token == "at-expired"
    assert result.expires_at is not None
    assert result.expires_at < datetime.now(UTC)


@pytest.mark.asyncio
async def test_get_valid_credential_refreshes_when_within_margin(
    respx_mock: MockRouter,
) -> None:
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        200,
        json={
            "access_token": "NEW",
            "refresh_token": "NEW_RT",
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
            refresh_token="OLD_RT",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
    )
    result = await get_valid_credential(
        "openai", alias="default", margin=timedelta(minutes=5), store=store
    )
    assert isinstance(result, OAuthCredential)
    assert result.access_token == "NEW"


@pytest.mark.asyncio
async def test_connect_stores_fingerprint_in_metadata(tmp_path: Path) -> None:
    store = MemoryStore()
    meta_store = MetadataStore(path=tmp_path / "metadata.json")
    method = get_method("openrouter", "api_key")
    await connect(
        "openrouter",
        alias="default",
        store=store,
        method=method,
        secret_prompt=lambda _p: "sk-or-test",
        metadata_store=meta_store,
    )
    entry = meta_store.get("openrouter", "default")
    assert entry is not None
    assert entry.fingerprint is not None
    assert len(entry.fingerprint) == 16


@pytest.mark.asyncio
async def test_refresh_raises_refresh_failed_on_503(
    respx_mock: MockRouter,
) -> None:
    respx_mock.post("https://auth.openai.com/oauth/token").respond(503)
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
    with pytest.raises(RefreshFailed):
        await refresh("openai", alias="default", store=store)


@pytest.mark.asyncio
async def test_refresh_network_error_raises_refresh_failed(
    respx_mock: MockRouter,
) -> None:
    """refresh() raises RefreshFailed on httpx network errors (ConnectError)."""
    respx_mock.post("https://auth.openai.com/oauth/token").mock(
        side_effect=httpx.ConnectError("connection refused")
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
    with pytest.raises(RefreshFailed):
        await refresh("openai", alias="default", store=store)


@pytest.mark.asyncio
async def test_refresh_entitlement_denied_raises_access_denied(
    respx_mock: MockRouter,
) -> None:
    """refresh() raises AccessDenied on entitlement_denied, not ReconnectionRequired."""
    respx_mock.post("https://auth.openai.com/oauth/token").respond(
        400, json={"error": "entitlement_denied"}
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
    with pytest.raises(AccessDenied):
        await refresh("openai", alias="default", store=store)


@pytest.mark.asyncio
async def test_concurrent_refresh_handles_race(
    stub_store: MemoryStore, respx_mock: MockRouter
) -> None:
    """Two concurrent refresh() calls: the server rejects the stale RT on the
    second call, but the first call's result is persisted."""
    original = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="chatgpt_oauth_browser",
        access_token="OLD_TOKEN",
        refresh_token="RT1",
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        scopes=[],
        client_id="test",
    )
    stub_store.set(original)

    call_count = 0

    def token_response(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "access_token": "NEW_TOKEN_1",
                    "refresh_token": "NEW_RT",
                    "expires_in": 3600,
                },
            )
        return httpx.Response(400, json={"error": "invalid_grant"})

    respx_mock.post("https://auth.openai.com/oauth/token").mock(
        side_effect=token_response
    )

    async def do_refresh() -> Credential:
        return await refresh("openai", alias="default", store=stub_store)

    results = await asyncio.gather(do_refresh(), do_refresh(), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, BaseException)]
    assert len(successes) >= 1, (
        f"Expected at least one success, got all errors: {results}"
    )

    stored = stub_store.get("openai", "default")
    assert stored is not None
    assert isinstance(stored, OAuthCredential)
    assert stored.access_token == "NEW_TOKEN_1"


@pytest.mark.asyncio
async def test_refresh_store_set_failure_after_token_success(
    respx_mock: MockRouter,
) -> None:
    """If store.set() fails after a successful token refresh, the exception
    propagates and the store is left untouched (no partial update)."""
    original = OAuthCredential(
        provider="openai",
        alias="default",
        method_id="chatgpt_oauth_browser",
        access_token="OLD_TOKEN",
        refresh_token="RT1",
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        scopes=[],
        client_id="test",
    )

    respx_mock.post("https://auth.openai.com/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "NEW_TOKEN",
                "refresh_token": "NEW_RT",
                "expires_in": 3600,
            },
        )
    )

    class FailingSetStore(MemoryStore):
        def set(self, credential: Credential) -> None:
            raise SecretStoreError("simulated store failure")

    failing = FailingSetStore()
    failing._entries[("openai", "default")] = original.model_dump_json()

    with pytest.raises(SecretStoreError, match="simulated store failure"):
        await refresh("openai", alias="default", store=failing)

    stored = failing.get("openai", "default")
    assert stored is not None
    assert isinstance(stored, OAuthCredential)
    assert stored.access_token == "OLD_TOKEN"
