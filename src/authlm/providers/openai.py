from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx
from typing_extensions import override

from authlm._auth_table import get_auth_entry, get_oauth_config
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.providers.base import ConnectionMethod, Provider


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
        self._entry = get_auth_entry("openai")

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
    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        client = self._http_client or httpx.AsyncClient()
        oauth = get_oauth_config("openai")
        assert oauth is not None
        methods: list[ConnectionMethod] = [
            APIKeyMethod(
                provider_id=self.id,
                secret_prompt=self._secret_prompt,
            ),
            OAuthPKCEMethod(
                provider_id=self.id,
                authorize_url=oauth.authorize_url,
                token_url=oauth.token_url,
                client_id=oauth.client_id,
                scopes=oauth.default_scopes,
                redirect_port=oauth.loopback_port or 1455,
                http_client=client,
            ),
        ]
        if oauth.device_code_url is not None:
            methods.append(
                OAuthDeviceCodeMethod(
                    provider_id=self.id,
                    device_code_url=oauth.device_code_url,
                    token_url=oauth.token_url,
                    client_id=oauth.client_id,
                    scopes=oauth.default_scopes,
                    http_client=client,
                )
            )
        return methods
