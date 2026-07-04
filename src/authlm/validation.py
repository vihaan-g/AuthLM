from __future__ import annotations

from collections.abc import Callable

import httpx

from authlm._auth_table import AUTH_TABLE
from authlm.connection_methods._oauth_helpers import redact_body
from authlm.credentials import ApiKeyCredential, Credential, OAuthCredential
from authlm.errors import AccessDenied, RefreshFailed, TokenEndpointError
from authlm.providers.registry import get_method as _get_method


async def validate(
    cred: Credential,
    *,
    force: bool,
    http_client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(
        timeout=15.0
    ),
) -> bool:
    """Probe whether a credential is currently usable.

    Refuses warned methods unless force=True. Returns True on 2xx, False on
    401/404. Raises AccessDenied on 403 with entitlement-denied, and
    TokenEndpointError on other 4xx. Raises RefreshFailed on network errors.
    """
    entry = AUTH_TABLE.get(cred.provider)
    if entry is None or entry.validation_url is None:
        return False

    method = _get_method(cred.provider, cred.method_id)
    if method.warning is not None and not force:
        raise PermissionError(
            f"validate() refuses warned method {cred.method_id!r}; "
            "pass force=True to probe anyway"
        )

    headers: dict[str, str] = {}
    if isinstance(cred, ApiKeyCredential):
        if cred.provider == "anthropic":
            headers["x-api-key"] = cred.secret
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {cred.secret}"
    elif isinstance(cred, OAuthCredential):
        headers["Authorization"] = f"Bearer {cred.access_token}"

    async with http_client_factory() as client:
        try:
            response = await client.get(str(entry.validation_url), headers=headers)
        except httpx.HTTPError as exc:
            raise RefreshFailed(f"validation probe failed: {exc}") from exc

    status = response.status_code
    if 200 <= status < 300:
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
