from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx
from typing_extensions import override

from authlm._auth_table import get_auth_entry, get_oauth_config
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.connection_methods.oauth_device import OAuthDeviceCodeMethod
from authlm.connection_methods.oauth_pkce import OAuthPKCEMethod
from authlm.providers.base import ConnectionMethod, Provider

ANTHROPIC_CLAUDE_PRO_WARNING = (
    "Anthropic prohibits this in their Terms of Service for non-Anthropic clients. "
    "Use at your own risk. Anthropic may revoke access or take action against accounts "
    "that use this method."
)


class AnthropicProvider(Provider):
    """Anthropic provider: api_key + warned Claude Pro OAuth (browser + headless)."""

    def __init__(
        self,
        *,
        secret_prompt: Callable[[str], str],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._secret_prompt = secret_prompt
        self._http_client = http_client
        self._entry = get_auth_entry("anthropic")

    @property
    @override
    def id(self) -> str:
        return "anthropic"

    @property
    @override
    def display_name(self) -> str:
        return "Anthropic"

    @property
    @override
    def docs_url(self) -> str | None:
        return "https://console.anthropic.com/settings/keys"

    @override
    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        client = self._http_client or httpx.AsyncClient()
        oauth = get_oauth_config("anthropic")
        assert oauth is not None

        api_key = APIKeyMethod(
            provider_id=self.id,
            secret_prompt=self._secret_prompt,
        )

        methods: list[ConnectionMethod] = [api_key]
        if not include_warned:
            return methods

        outer = self
        port = oauth.loopback_port or 5454

        class _WarnedPKCE(OAuthPKCEMethod):
            @property
            @override
            def id(self) -> str:
                return "claude_pro_oauth_browser"

            @property
            @override
            def label(self) -> str:
                return "Claude Pro/Max (browser)"

            @property
            @override
            def warning(self) -> str | None:
                return ANTHROPIC_CLAUDE_PRO_WARNING

            @override
            def with_open_browser(self, callback: Callable[[str], None]) -> _WarnedPKCE:
                return _WarnedPKCE(
                    provider_id=self._provider_id,
                    authorize_url=self._authorize_url,
                    token_url=self._token_url,
                    client_id=self._client_id,
                    scopes=self._scopes,
                    redirect_port=self._redirect_port,
                    redirect_path=self._redirect_path,
                    loopback_factory=self._loopback_factory,
                    open_browser=callback,
                    http_client=self._http_client,
                )

        methods.append(
            _WarnedPKCE(
                provider_id=outer.id,
                authorize_url=oauth.authorize_url,
                token_url=oauth.token_url,
                client_id=oauth.client_id,
                scopes=oauth.default_scopes,
                redirect_port=port,
                http_client=client,
            )
        )
        if oauth.device_code_url is not None:

            class _WarnedDevice(OAuthDeviceCodeMethod):
                @property
                @override
                def id(self) -> str:
                    return "claude_pro_oauth_device"

                @property
                @override
                def label(self) -> str:
                    return "Claude Pro/Max (headless)"

                @property
                @override
                def warning(self) -> str | None:
                    return ANTHROPIC_CLAUDE_PRO_WARNING

                @override
                def with_on_prompt(
                    self, callback: Callable[[str, str], None]
                ) -> _WarnedDevice:
                    return _WarnedDevice(
                        provider_id=self._provider_id,
                        device_code_url=self._device_code_url,
                        token_url=self._token_url,
                        client_id=self._client_id,
                        scopes=self._scopes,
                        on_prompt=callback,
                        poll_interval_seconds=self._poll_interval_seconds,
                        poll_timeout_seconds=self._poll_timeout_seconds,
                        http_client=self._http_client,
                    )

            methods.append(
                _WarnedDevice(
                    provider_id=outer.id,
                    device_code_url=oauth.device_code_url,
                    token_url=oauth.token_url,
                    client_id=oauth.client_id,
                    scopes=oauth.default_scopes,
                    http_client=client,
                )
            )
        return methods
