from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx
from typing_extensions import override

from authlm._auth_table import get_oauth_config
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.providers.base import ConnectionMethod, Provider


class _GoogleOAuthBrowser(OAuthPKCEMethod):
    @property
    @override
    def id(self) -> str:
        return "oauth_browser"

    @property
    @override
    def label(self) -> str:
        return "Google AI Studio (browser)"

    @override
    def with_open_browser(self, callback: Callable[[str], None]) -> _GoogleOAuthBrowser:
        return _GoogleOAuthBrowser(
            provider_id=self._provider_id,
            authorize_url=self._authorize_url,
            token_url=self._token_url,
            client_id=self._client_id,
            scopes=self._scopes,
            redirect_port=self._redirect_port,
            extra_authorize_params=self._extra_authorize_params,
            loopback_factory=self._loopback_factory,
            open_browser=callback,
            http_client=self._http_client,
        )


class GoogleProvider(Provider):
    """Google AI provider: api_key + AI Studio OAuth (browser)."""

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
        return "google"

    @property
    @override
    def display_name(self) -> str:
        return "Google AI"

    @property
    @override
    def docs_url(self) -> str | None:
        return "https://aistudio.google.com/apikey"

    @override
    def connection_methods(
        self, *, include_warned: bool, http_client: httpx.AsyncClient | None = None
    ) -> Sequence[ConnectionMethod]:
        client = http_client or self._http_client or httpx.AsyncClient()
        oauth = get_oauth_config("google")
        assert oauth is not None
        return [
            APIKeyMethod(
                provider_id=self.id,
                secret_prompt=self._secret_prompt,
            ),
            _GoogleOAuthBrowser(
                provider_id=self.id,
                authorize_url=oauth.authorize_url,
                token_url=oauth.token_url,
                client_id=oauth.client_id,
                scopes=oauth.default_scopes,
                redirect_port=oauth.loopback_port or 8085,
                extra_authorize_params=oauth.extra_authorize_params,
                http_client=client,
            ),
        ]
