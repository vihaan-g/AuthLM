from __future__ import annotations

from datetime import UTC, datetime

import httpx

from authlm._auth_table import AUTH_TABLE
from authlm.connection_methods._oauth_helpers import redact_body
from authlm.credentials import ApiKeyCredential, Credential, OAuthCredential
from authlm.errors import AccessDenied, AuthLMError, RefreshFailed, TokenEndpointError
from authlm.metadata import MetadataEntry, MetadataStore
from authlm.providers.registry import get_method as _get_method
from authlm.providers.registry import get_provider as _get_provider


async def validate(
    cred: Credential,
    *,
    force: bool,
    metadata_store: MetadataStore | None = None,
) -> bool:
    """Probe whether a credential is currently usable.

    Refuses warned methods unless force=True. Returns True on 2xx, False on
    401/404. Raises AccessDenied on 403 with entitlement-denied, and
    TokenEndpointError on other 4xx. Raises RefreshFailed on network errors.

    Raises:
        PermissionError: If the method is warned and force=False.
        AuthLMError: If validation probe is not supported for credential
            (e.g. ChatGPT OAuth).
        AccessDenied: On 403 response from probe endpoint.
        TokenEndpointError: On 4xx response (other than 401/403/404) from
            probe endpoint.
        RefreshFailed: On network error or 5xx response from probe endpoint.
    """

    entry = AUTH_TABLE.get(cred.provider)
    if cred.provider == "openai" and cred.method_id in (
        "chatgpt_oauth_browser",
        "chatgpt_oauth_device",
    ):
        raise AuthLMError(
            "Validation probe not supported for ChatGPT OAuth tokens; "
            "use direct inference to verify."
        )

    if entry is None or entry.validation_url is None:
        return False

    method = _get_method(cred.provider, cred.method_id)
    if method.warning is not None and not force:
        raise PermissionError(
            f"validate() refuses warned method {cred.method_id!r}; "
            "pass force=True to probe anyway"
        )

    headers: dict[str, str] = {}
    params: dict[str, str] = {}
    if isinstance(cred, ApiKeyCredential):
        if cred.provider == "anthropic":
            headers["x-api-key"] = cred.secret
            headers["anthropic-version"] = "2023-06-01"
        elif entry.validation_api_key_query_param is not None:
            params[entry.validation_api_key_query_param] = cred.secret
        else:
            headers["Authorization"] = f"Bearer {cred.secret}"
    elif isinstance(cred, OAuthCredential):
        headers["Authorization"] = f"Bearer {cred.access_token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                str(entry.validation_url), headers=headers, params=params
            )
        except httpx.HTTPError as exc:
            raise RefreshFailed(f"validation probe failed: {exc}") from exc

    status = response.status_code
    if 200 <= status < 300:
        if metadata_store is not None:
            meta = metadata_store.get(cred.provider, cred.alias)
            if meta is None:
                meta = MetadataEntry(
                    provider_display_name=_get_provider(cred.provider).display_name,
                    method_id=cred.method_id,
                    connected_at=datetime.now(UTC),
                    last_validated_at=datetime.now(UTC),
                )
            else:
                meta.last_validated_at = datetime.now(UTC)
            metadata_store.set(cred.provider, cred.alias, meta)
        return True
    if status in {401, 404}:
        return False
    if status == 403:
        raise AccessDenied("validation probe: 403 (token may lack entitlement)")
    if 400 <= status < 500:
        raise TokenEndpointError(
            f"validation probe: status={status} body={redact_body(response.text)}"
        )
    raise RefreshFailed(f"validation probe: status={status} (provider may be down)")
