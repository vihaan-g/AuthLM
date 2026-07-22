from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from typing import Any, cast

import httpx
from pydantic import BaseModel, HttpUrl, ValidationError
from typing_extensions import override

from authlm._auth_table import get_oauth_config
from authlm.connection_methods._oauth_helpers import (
    build_oauth_credential,
    classify_token_error,
    redact_body,
    redact_url,
)
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.credentials import Credential, OAuthCredential
from authlm.errors import (
    AccessDenied,
    ConnectionTimeout,
    ReconnectionRequired,
    RefreshFailed,
    TokenEndpointError,
)
from authlm.providers.base import ConnectionMethod, Provider
from authlm.stores.base import CredentialStore


class _ChatGPTDeviceUserCode(BaseModel):
    device_auth_id: str
    user_code: str
    interval: int = 5


class _ChatGPTDeviceAuthorizationCode(BaseModel):
    authorization_code: str
    code_challenge: str
    code_verifier: str


class _ChatGPTBrowserPKCE(OAuthPKCEMethod):
    @property
    @override
    def id(self) -> str:
        return "chatgpt_oauth_browser"

    @property
    @override
    def label(self) -> str:
        return "ChatGPT Pro/Plus (browser)"

    @override
    def with_open_browser(self, callback: Callable[[str], None]) -> _ChatGPTBrowserPKCE:
        return _ChatGPTBrowserPKCE(
            provider_id=self._provider_id,
            authorize_url=self._authorize_url,
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            redirect_port=self._redirect_port,
            fixed_redirect_uri=self._fixed_redirect_uri,
            extra_authorize_params=self._extra_authorize_params,
            loopback_factory=self._loopback_factory,
            open_browser=callback,
            http_client=self._http_client,
        )


class _ChatGPTDevice(OAuthDeviceCodeMethod):
    def __init__(
        self,
        *,
        provider_id: str,
        device_code_url: HttpUrl,
        device_code_poll_url: HttpUrl,
        device_code_verification_uri: HttpUrl,
        device_code_redirect_uri: HttpUrl,
        token_url: HttpUrl,
        client_id: str,
        scopes: Sequence[str],
        on_prompt: Callable[[str, str], None] | None = None,
        poll_interval_seconds: float = 5.0,
        poll_timeout_seconds: float = 900.0,
        http_client: httpx.AsyncClient | None = None,
        device_code_content_type: str = "application/x-www-form-urlencoded",
    ) -> None:
        super().__init__(
            provider_id=provider_id,
            device_code_url=device_code_url,
            token_url=token_url,
            client_id=client_id,
            scopes=scopes,
            on_prompt=on_prompt,
            poll_interval_seconds=poll_interval_seconds,
            poll_timeout_seconds=poll_timeout_seconds,
            http_client=http_client,
            device_code_content_type=device_code_content_type,
        )
        self._device_code_poll_url = device_code_poll_url
        self._device_code_verification_uri = device_code_verification_uri
        self._device_code_redirect_uri = device_code_redirect_uri

    @property
    @override
    def id(self) -> str:
        return "chatgpt_oauth_device"

    @property
    @override
    def label(self) -> str:
        return "ChatGPT Pro/Plus (headless)"

    @override
    def with_on_prompt(self, callback: Callable[[str, str], None]) -> _ChatGPTDevice:
        return _ChatGPTDevice(
            provider_id=self._provider_id,
            device_code_url=self._device_code_url,
            device_code_poll_url=self._device_code_poll_url,
            device_code_verification_uri=self._device_code_verification_uri,
            device_code_redirect_uri=self._device_code_redirect_uri,
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            on_prompt=callback,
            poll_interval_seconds=self._poll_interval_seconds,
            poll_timeout_seconds=self._poll_timeout_seconds,
            http_client=self._http_client,
            device_code_content_type=self._device_code_content_type,
        )

    @override
    async def connect(self, *, store: CredentialStore) -> Credential:
        del store
        if self._http_client is not None:
            return await self._connect_with_client(self._http_client)
        async with httpx.AsyncClient() as client:
            return await self._connect_with_client(client)

    async def _connect_with_client(self, client: httpx.AsyncClient) -> Credential:
        user_code = await self._request_user_code(client=client)
        self._on_prompt(
            str(self._device_code_verification_uri),
            user_code.user_code,
        )
        authorization_code = await self._poll_for_authorization_code(
            user_code, client=client
        )
        return await self._exchange_authorization_code(
            authorization_code, client=client
        )

    async def _request_user_code(
        self, *, client: httpx.AsyncClient | None = None
    ) -> _ChatGPTDeviceUserCode:
        http_client = client or self._http_client
        if http_client is None:
            raise RuntimeError("http_client is required")
        try:
            response = await http_client.post(
                str(self._device_code_url),
                json={"client_id": self._client_id},
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
            return _ChatGPTDeviceUserCode.model_validate(response.json())
        except (json.JSONDecodeError, ValidationError) as exc:
            raise TokenEndpointError(
                f"Device-code endpoint returned invalid JSON: "
                f"body={redact_body(response.text)}"
            ) from exc

    async def _poll_for_authorization_code(
        self,
        user_code: _ChatGPTDeviceUserCode,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> _ChatGPTDeviceAuthorizationCode:
        http_client = client or self._http_client
        if http_client is None:
            raise RuntimeError("http_client is required")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._poll_timeout_seconds
        while True:
            response = await http_client.post(
                str(self._device_code_poll_url),
                json={
                    "device_auth_id": user_code.device_auth_id,
                    "user_code": user_code.user_code,
                },
                timeout=30.0,
            )
            if 200 <= response.status_code < 300:
                try:
                    return _ChatGPTDeviceAuthorizationCode.model_validate(
                        response.json()
                    )
                except (json.JSONDecodeError, ValidationError) as exc:
                    raise TokenEndpointError(
                        f"Device-code poll endpoint returned invalid JSON: "
                        f"body={redact_body(response.text)}"
                    ) from exc
            if response.status_code in (403, 404):
                if loop.time() >= deadline:
                    raise ConnectionTimeout("Device-code flow timed out")
                await asyncio.sleep(float(user_code.interval))
                continue
            raise TokenEndpointError(
                f"Device-code poll failed: status={response.status_code} "
                f"body={redact_body(response.text)}"
            )

    async def _exchange_authorization_code(
        self,
        authorization_code: _ChatGPTDeviceAuthorizationCode,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> OAuthCredential:
        http_client = client or self._http_client
        if http_client is None:
            raise RuntimeError("http_client is required")
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": authorization_code.authorization_code,
            "redirect_uri": str(self._device_code_redirect_uri),
            "client_id": self._client_id,
            "code_verifier": authorization_code.code_verifier,
        }
        try:
            response = await http_client.post(
                str(self._token_url), data=payload, timeout=30.0
            )
        except httpx.HTTPError as exc:
            raise RefreshFailed(
                f"Token exchange network error for {self._provider_id}: "
                f"POST {redact_url(str(self._token_url))}"
            ) from exc
        classification = classify_token_error(
            status_code=response.status_code, body=response.text
        )
        if classification.fatal:
            if classification.fatal_reason == "access_denied":
                raise AccessDenied(
                    f"Token exchange error for {self._provider_id}: "
                    f"{classification.error_code}"
                )
            code = classification.error_code or str(response.status_code)
            raise ReconnectionRequired(f"Token endpoint returned {code}")
        if 500 <= response.status_code < 600:
            raise RefreshFailed(
                f"Token exchange server error for {self._provider_id}: "
                f"HTTP {response.status_code}"
            )
        if not (200 <= response.status_code < 300):
            raise TokenEndpointError(
                f"Token endpoint error: status={response.status_code} "
                f"body={redact_body(response.text)}"
            )
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise TokenEndpointError(
                f"Token endpoint returned non-JSON body: "
                f"body={redact_body(response.text)}"
            ) from exc
        if not isinstance(data, dict):
            raise TokenEndpointError("Token endpoint returned a non-object JSON body")
        return build_oauth_credential(
            data=cast(dict[str, Any], data),
            provider=self._provider_id,
            alias="default",
            method_id=self.id,
            client_id=self._client_id,
        )


class OpenAIProvider(Provider):
    """OpenAI provider: api_key + ChatGPT OAuth (PKCE) + ChatGPT OAuth (device-code)."""

    def __init__(
        self,
        *,
        secret_prompt: Callable[[str], str],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._secret_prompt = secret_prompt
        self._http_client = http_client

    @property
    @override
    def id(self) -> str:
        return "openai"

    @property
    @override
    def display_name(self) -> str:
        return "OpenAI"

    @property
    @override
    def docs_url(self) -> str | None:
        return "https://platform.openai.com/api-keys"

    @override
    def connection_methods(
        self, *, include_warned: bool, http_client: httpx.AsyncClient | None = None
    ) -> Sequence[ConnectionMethod]:
        client = http_client or self._http_client
        oauth = get_oauth_config("openai")
        assert oauth is not None
        assert oauth.fixed_redirect_uri is not None
        methods: list[ConnectionMethod] = [
            APIKeyMethod(
                provider_id=self.id,
                secret_prompt=self._secret_prompt,
            ),
            _ChatGPTBrowserPKCE(
                provider_id=self.id,
                authorize_url=oauth.authorize_url,
                token_url=oauth.token_url,
                client_id=oauth.client_id,
                scopes=oauth.default_scopes,
                redirect_port=oauth.loopback_port or 1455,
                fixed_redirect_uri=str(oauth.fixed_redirect_uri),
                extra_authorize_params=oauth.extra_authorize_params,
                http_client=client,
            ),
        ]
        if oauth.device_code_url is not None:
            assert oauth.device_code_poll_url is not None
            assert oauth.device_code_verification_uri is not None
            assert oauth.device_code_redirect_uri is not None
            methods.append(
                _ChatGPTDevice(
                    provider_id=self.id,
                    device_code_url=oauth.device_code_url,
                    device_code_poll_url=oauth.device_code_poll_url,
                    device_code_verification_uri=oauth.device_code_verification_uri,
                    device_code_redirect_uri=oauth.device_code_redirect_uri,
                    token_url=oauth.token_url,
                    client_id=oauth.client_id,
                    scopes=oauth.default_scopes,
                    http_client=client,
                    device_code_content_type=oauth.device_code_content_type,
                )
            )
        return methods
