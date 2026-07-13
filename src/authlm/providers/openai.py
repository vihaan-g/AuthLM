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
    PKCEPair,
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
    interval: int = 0


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
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            on_prompt=callback,
            poll_interval_seconds=self._poll_interval_seconds,
            poll_timeout_seconds=self._poll_timeout_seconds,
            http_client=self._http_client,
            device_code_content_type=self._device_code_content_type,
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
        client = http_client or self._http_client or httpx.AsyncClient()
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
            methods.append(
                _ChatGPTDevice(
                    provider_id=self.id,
                    device_code_url=oauth.device_code_url,
                    token_url=oauth.token_url,
                    client_id=oauth.client_id,
                    scopes=oauth.default_scopes,
                    http_client=client,
                    device_code_content_type=oauth.device_code_content_type,
                )
            )
        return methods
