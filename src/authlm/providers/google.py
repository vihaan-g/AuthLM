from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx
from typing_extensions import override

from authlm._auth_table import get_auth_entry
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.providers.base import ConnectionMethod, Provider


class GoogleProvider(Provider):
    def __init__(
        self,
        *,
        secret_prompt: Callable[[str], str],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._secret_prompt = secret_prompt
        self._http_client = http_client
        self._entry = get_auth_entry("google")

    @property
    @override
    def id(self) -> str:
        return "google"

    @property
    @override
    def display_name(self) -> str:
        return "Google AI"

    @property
    @override
    def docs_url(self) -> str | None:
        return "https://aistudio.google.com/apikey"

    @property
    @override
    def logo_url(self) -> str | None:
        return None

    @override
    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        client = self._http_client or httpx.AsyncClient()
        oauth = self._entry.oauth
        assert oauth is not None
        return [
            APIKeyMethod(
                provider_id=self.id,
                secret_prompt=self._secret_prompt,
                validation_url=str(self._entry.validation_url)
                if self._entry.validation_url
                else None,
            ),
            OAuthPKCEMethod(
                provider_id=self.id,
                authorize_url=oauth.authorize_url,
                token_url=oauth.token_url,
                client_id=oauth.client_id,
                scopes=oauth.default_scopes,
                redirect_port=oauth.loopback_port or 8085,
                http_client=client,
            ),
        ]
