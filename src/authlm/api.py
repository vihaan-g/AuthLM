from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

from authlm._auth_table import get_oauth_config
from authlm.connection_methods._oauth_helpers import (
    build_oauth_credential,
    classify_token_error,
    redact_body,
)
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.credentials import (
    ApiKeyCredential,
    Credential,
    OAuthCredential,
    compute_fingerprint,
)
from authlm.errors import (
    AccessDenied,
    AuthLMError,
    CredentialNotFound,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.metadata import MetadataEntry, MetadataStore
from authlm.providers.base import ConnectionMethod
from authlm.providers.registry import get_method as _get_method
from authlm.providers.registry import get_provider as _get_provider
from authlm.stores import get_default_store
from authlm.stores.base import CredentialStore


def should_refresh(cred: Credential, *, margin: timedelta) -> bool:
    """Return True if the credential is expired or within margin of expiry.

    Args:
        cred: The credential to check.
        margin: If the credential expires within this window, it is
            considered in need of refresh.

    Returns:
        True if the credential should be refreshed. For credentials
        without ``expires_at`` (e.g. ``ApiKeyCredential``), returns False.

    Sync — pure datetime arithmetic, no I/O. Safe to call from any context.
    """
    if not isinstance(cred, OAuthCredential) or cred.expires_at is None:
        return False
    now = datetime.now(UTC)
    return cred.expires_at <= now + margin


async def get_credential(
    provider: str,
    *,
    alias: str,
    store: CredentialStore | None = None,
) -> Credential:
    """Return the stored credential as-is, even if expired.

    Fast store read, no network. Use when you need the raw credential value
    and will check expiry yourself. For automatic refresh, use
    ``get_valid_credential``.

    Args:
        provider: Provider ID (e.g. ``"openai"``).
        alias: Credential alias (e.g. ``"default"``).
        store: Credential store backend. Uses ``get_default_store()`` if
            ``None``.

    Returns:
        The stored credential.

    Raises:
        CredentialNotFound: No credential stored for (provider, alias).
    """
    backend = store or get_default_store()
    cred = backend.get(provider, alias)
    if cred is None:
        raise CredentialNotFound(f"No credential stored for {provider}:{alias}")
    return cred


async def get_valid_credential(
    provider: str,
    *,
    alias: str,
    margin: timedelta,
    store: CredentialStore | None = None,
    metadata_store: MetadataStore | None = None,
) -> Credential:
    """Return a credential that is currently usable.

    If the credential is expired or within ``margin`` of expiry, attempts
    a refresh via the provider's token endpoint. Makes a network call only
    when refresh is needed.

    Args:
        provider: Provider ID (e.g. ``"openai"``).
        alias: Credential alias (e.g. ``"default"``).
        margin: Refresh window. Recommended: ``timedelta(minutes=5)``.
        store: Credential store backend. Uses ``get_default_store()`` if
            ``None``.
        metadata_store: Optional metadata store for fingerprint updates
            after refresh.

    Returns:
        A valid credential, refreshed if necessary.

    Raises:
        CredentialNotFound: No credential stored for (provider, alias).
        ReconnectionRequired: Refresh token is dead; re-run ``connect()``.
        RefreshFailed: Transient network error from token endpoint.
        TokenEndpointError: Other token endpoint error.
    """
    backend = store or get_default_store()
    cred = backend.get(provider, alias)
    if cred is None:
        raise CredentialNotFound(f"No credential stored for {provider}:{alias}")
    if should_refresh(cred, margin=margin):
        return await refresh(
            provider, alias=alias, store=backend, metadata_store=metadata_store
        )
    return cred


async def refresh(
    provider: str,
    *,
    alias: str,
    store: CredentialStore | None = None,
    metadata_store: MetadataStore | None = None,
) -> Credential:
    """Force-refresh the credential regardless of expiry.

    POSTs to the provider's token endpoint with the stored refresh token.
    Persists the new access token and (if provided) the new refresh token.
    If the server omits a new refresh token, the old one is kept.

    Args:
        provider: Provider ID (e.g. ``"openai"``).
        alias: Credential alias (e.g. ``"default"``).
        store: Credential store backend. Uses ``get_default_store()`` if
            ``None``.
        metadata_store: Optional metadata store for fingerprint updates
            after refresh.

    Returns:
        The refreshed credential.

    Raises:
        CredentialNotFound: No credential stored for (provider, alias).
        ReconnectionRequired: Refresh token is dead (invalid_grant);
            re-run ``connect()``.
        RefreshFailed: Transient network error or 5xx from token endpoint.
        TokenEndpointError: Other token endpoint error.
        AuthLMError: Provider has no OAuth config.
    """
    backend = store or get_default_store()
    cred = backend.get(provider, alias)
    if cred is None:
        raise CredentialNotFound(f"No credential stored for {provider}:{alias}")
    if not isinstance(cred, OAuthCredential):
        return cred
    if not cred.refresh_token:
        raise ReconnectionRequired(
            f"No refresh token for {provider}:{alias}; re-run connect()"
        )
    oauth = get_oauth_config(provider)
    if oauth is None:
        raise AuthLMError(f"Provider {provider!r} has no OAuth config")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                str(oauth.token_url),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": cred.refresh_token,
                    "client_id": oauth.client_id,
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise RefreshFailed(
                f"Token endpoint network error for {provider}:{alias}: {exc}"
            ) from exc
    classification = classify_token_error(
        status_code=response.status_code, body=response.text
    )
    if classification.fatal:
        if classification.fatal_reason == "access_denied":
            raise AccessDenied(
                f"Token refresh for {provider}:{alias}: {classification.error_code}"
            )
        raise ReconnectionRequired(
            f"Refresh token for {provider}:{alias} is dead; "
            f"re-run connect() ({classification.error_code})"
        )
    if 500 <= response.status_code < 600:
        raise RefreshFailed(f"Token endpoint 5xx: status={response.status_code}")
    if not (200 <= response.status_code < 300):
        raise TokenEndpointError(
            f"Token endpoint error: status={response.status_code} "
            f"body={redact_body(response.text)}"
        )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise TokenEndpointError(
            f"Token endpoint returned non-JSON body: body={redact_body(response.text)}"
        ) from exc
    new_cred = build_oauth_credential(
        data=data,
        provider=cred.provider,
        alias=cred.alias,
        method_id=cred.method_id,
        client_id=cred.client_id,
    )
    update: dict[str, object] = {}
    if new_cred.refresh_token is None and cred.refresh_token is not None:
        update["refresh_token"] = cred.refresh_token
    if not new_cred.scopes and cred.scopes:
        update["scopes"] = list(cred.scopes)
    update["warning_acknowledged_at"] = cred.warning_acknowledged_at
    new_cred = new_cred.model_copy(update=update)
    backend.set(new_cred)
    if metadata_store is not None:
        fp = compute_fingerprint(new_cred.access_token)
        meta = metadata_store.get(provider, alias)
        if meta is not None:
            meta.fingerprint = fp
            metadata_store.set(provider, alias, meta)
    return new_cred


async def connect(
    provider: str,
    *,
    alias: str,
    method: ConnectionMethod | None = None,
    method_id: str | None = None,
    store: CredentialStore | None = None,
    secret_prompt: Callable[[str], str] | None = None,
    on_prompt: Callable[[str, str], None] | None = None,
    open_browser: Callable[[str], None] | None = None,
    metadata_store: MetadataStore | None = None,
) -> Credential:
    """Run a connection method interactively and persist the resulting credential.

    Looks up the provider, selects a connection method (if not already
    provided), runs its interactive auth flow, persists the credential to
    the store, and updates metadata including the secret fingerprint.

    Note: each ConnectionMethod's connect() returns a Credential with
    alias="default". We re-key it to the requested alias here.

    Args:
        provider: Provider ID (e.g. ``"openai"``, ``"anthropic"``).
        alias: Label for this credential (e.g. ``"default"``, ``"personal"``).
        method: A pre-built ConnectionMethod instance. Overrides ``method_id``.
        method_id: Method ID to use (e.g. ``"api_key"``,
            ``"chatgpt_oauth_browser"``). Required if ``method`` is not provided.
        store: CredentialStore to persist to. Uses ``get_default_store()`` if
            ``None``.
        secret_prompt: Callback for interactive secret entry. The CLI injects
            a Click-aware prompt; library consumers may omit.
        on_prompt: Callback for device-code prompts (URI and user code). The
            CLI injects a stderr echo; library consumers may omit.
        open_browser: Callback to open the OAuth authorize URL. The CLI
            injects ``webbrowser.open``; library consumers may omit.
        metadata_store: MetadataStore for non-secret metadata. If provided,
            fingerprint and timestamps are persisted.

    Returns:
        The persisted Credential.

    Raises:
        AuthLMError: Unknown provider or missing method specification.
        SecretStoreError: Store persistence failure.
    """
    backend = store or get_default_store()
    if method is None:
        if method_id is None:
            raise AuthLMError("connect() requires either method or method_id")
        method = _get_method(provider, method_id)

    if isinstance(method, APIKeyMethod) and secret_prompt is not None:
        method = method.with_secret_prompt(secret_prompt)
    if isinstance(method, OAuthDeviceCodeMethod) and on_prompt is not None:
        method = method.with_on_prompt(on_prompt)
    if isinstance(method, OAuthPKCEMethod) and open_browser is not None:
        method = method.with_open_browser(open_browser)

    cred = await method.connect(store=backend)
    if cred.alias != alias:
        cred = cred.model_copy(update={"alias": alias})
    if method.warning:
        cred = cred.model_copy(update={"warning_acknowledged_at": datetime.now(UTC)})
    backend.set(cred)

    if metadata_store is not None:
        secret_value: str | None = None
        if isinstance(cred, ApiKeyCredential):
            secret_value = cred.secret
        elif isinstance(cred, OAuthCredential):
            secret_value = cred.access_token

        entry = MetadataEntry(
            provider_display_name=_get_provider(provider).display_name,
            method_id=cred.method_id,
            connected_at=datetime.now(UTC),
            scopes=list(cred.scopes) if isinstance(cred, OAuthCredential) else [],
            warning_acknowledged_at=datetime.now(UTC) if method.warning else None,
            client_id=cred.client_id if isinstance(cred, OAuthCredential) else None,
            fingerprint=compute_fingerprint(secret_value) if secret_value else None,
        )
        metadata_store.set(provider, alias, entry)

    return cred
