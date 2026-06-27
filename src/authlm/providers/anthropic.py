from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx
from typing_extensions import override

from authlm._auth_table import get_auth_entry
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

    @property
    @override
    def logo_url(self) -> str | None:
        return None

    @override
    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        client = self._http_client or httpx.AsyncClient()
        oauth = self._entry.oauth
        assert oauth is not None

        api_key = APIKeyMethod(
            provider_id=self.id,
            secret_prompt=self._secret_prompt,
            validation_url=str(self._entry.validation_url)
            if self._entry.validation_url
            else None,
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
