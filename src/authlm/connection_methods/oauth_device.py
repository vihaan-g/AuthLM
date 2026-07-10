from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Sequence
from typing import Any, cast

import httpx
from pydantic import HttpUrl
from typing_extensions import override

from authlm.connection_methods._oauth_helpers import (
    build_oauth_credential,
    classify_token_error,
    redact_body,
    redact_url,
)
from authlm.credentials import Credential
from authlm.errors import (
    AccessDenied,
    ConnectionTimeout,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores.base import CredentialStore

_log = logging.getLogger(__name__)


def _default_on_prompt(uri: str, user_code: str) -> None:
    _log.info("Open %s and enter code: %s", uri, user_code)


class OAuthDeviceCodeMethod(ConnectionMethod):
    """OAuth device-code flow: print prompt, poll token endpoint until authorized."""

    def __init__(
        self,
        *,
        provider_id: str,
        device_code_url: HttpUrl,
        token_url: HttpUrl,
        client_id: str,
        scopes: Sequence[str],
        on_prompt: Callable[[str, str], None] | None = None,
        poll_interval_seconds: float = 5.0,
        poll_timeout_seconds: float = 900.0,
        http_client: httpx.AsyncClient | None = None,
        device_code_content_type: str = "application/x-www-form-urlencoded",
    ) -> None:
        self._provider_id = provider_id
        self._device_code_url = device_code_url
        self._token_url = token_url
        self._client_id = client_id
        self._scopes: tuple[str, ...] = tuple(scopes)
        self._on_prompt = on_prompt or _default_on_prompt
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._http_client = http_client
        self._device_code_content_type = device_code_content_type

    def with_on_prompt(
        self, callback: Callable[[str, str], None]
    ) -> OAuthDeviceCodeMethod:
        """Return a new instance with the given on_prompt callback.

        Mirrors ``APIKeyMethod.with_secret_prompt``; the CLI uses this
        to inject a Click-aware prompt.
        """
        return OAuthDeviceCodeMethod(
            provider_id=self._provider_id,
            device_code_url=self._device_code_url,
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            on_prompt=callback,
            poll_interval_seconds=self._poll_interval_seconds,
            poll_timeout_seconds=self._poll_timeout_seconds,
            http_client=self._http_client,
            device_code_content_type=self._device_code_content_type,
        )

    @property
    @override
    def id(self) -> str:
        return "oauth_device"

    @property
    @override
    def label(self) -> str:
        return "Device-code OAuth"

    @property
    @override
    def warning(self) -> str | None:
        return None

    @property
    @override
    def oauth_grant(self) -> OAuthGrant | None:
        return OAuthGrant.DEVICE_CODE

    @override
    async def connect(self, *, store: CredentialStore) -> Credential:
        if self._http_client is None:
            raise RuntimeError("http_client is required for connect()")
        device = await self._request_device_code()
        self._on_prompt(str(device["verification_uri"]), str(device["user_code"]))

        effective_interval: float = self._poll_interval_seconds
        server_interval = device.get("interval")
        if isinstance(server_interval, (int, float)):
            effective_interval = max(
                float(server_interval), self._poll_interval_seconds
            )

        effective_timeout: float = self._poll_timeout_seconds
        server_expires = device.get("expires_in")
        if isinstance(server_expires, (int, float)):
            effective_timeout = min(float(server_expires), self._poll_timeout_seconds)

        token = await self._poll_for_token(
            str(device["device_code"]),
            interval=effective_interval,
            timeout=effective_timeout,
        )
        return build_oauth_credential(
            data=token,
            provider=self._provider_id,
            alias="default",
            method_id=self.id,
            client_id=self._client_id,
        )

    async def _request_device_code(self) -> dict[str, Any]:
        assert self._http_client is not None
        body: dict[str, str] = {
            "client_id": self._client_id,
            "scope": " ".join(self._scopes),
        }
        try:
            if self._device_code_content_type == "application/json":
                response = await self._http_client.post(
                    str(self._device_code_url),
                    json=body,
                    timeout=30.0,
                )
            else:
                response = await self._http_client.post(
                    str(self._device_code_url),
                    data=body,
                    timeout=30.0,
                )
        except httpx.HTTPError as exc:
            raise RefreshFailed(
                f"Device-code request network error for {self._provider_id}"
            ) from exc
        if not (200 <= response.status_code < 300):
            if 500 <= response.status_code < 600:
                raise RefreshFailed(
                    f"Device-code request server error for {self._provider_id}: "
                    f"HTTP {response.status_code}"
                )
            raise TokenEndpointError(
                f"device-code request failed: status={response.status_code} "
                f"body={redact_body(response.text)}"
            )
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise TokenEndpointError(
                f"Device-code endpoint returned non-JSON body: "
                f"body={redact_body(response.text)}"
            ) from exc
        if (
            not isinstance(data, dict)
            or "device_code" not in data
            or "user_code" not in data
        ):
            raise TokenEndpointError("device-code response missing fields")
        return cast(dict[str, Any], data)

    async def _poll_for_token(
        self, device_code: str, *, interval: float, timeout: float
    ) -> dict[str, Any]:
        assert self._http_client is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            _log.debug("POST %s", redact_url(str(self._token_url)))
            response = await self._http_client.post(
                str(self._token_url),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": self._client_id,
                },
                timeout=30.0,
            )
            if 200 <= response.status_code < 300:
                try:
                    return cast(dict[str, Any], response.json())
                except json.JSONDecodeError as exc:
                    raise TokenEndpointError(
                        f"Token endpoint returned non-JSON body: "
                        f"body={redact_body(response.text)}"
                    ) from exc
            classification = classify_token_error(
                status_code=response.status_code, body=response.text
            )
            if classification.fatal:
                if classification.fatal_reason == "access_denied":
                    raise AccessDenied(
                        f"Device-code token error for {self._provider_id}: "
                        f"{classification.error_code}"
                    )
                raise ReconnectionRequired(
                    f"Device-code flow failed fatally: {classification.error_code}"
                )
            if classification.error_code in ("authorization_pending", "slow_down"):
                if loop.time() >= deadline:
                    raise ConnectionTimeout("Device-code flow timed out")
                if classification.error_code == "slow_down":
                    interval += 5.0
                await asyncio.sleep(interval)
                continue
            if classification.status_code >= 500 or classification.status_code == 0:
                await asyncio.sleep(interval)
                continue
            raise TokenEndpointError(
                f"Token endpoint error: status={response.status_code} "
                f"body={redact_body(response.text)}"
            )
