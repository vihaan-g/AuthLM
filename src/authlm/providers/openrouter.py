from __future__ import annotations

from collections.abc import Callable, Sequence

from typing_extensions import override

from authlm._auth_table import get_auth_entry
from authlm.connection_methods.api_key import APIKeyMethod
from authlm.providers.base import ConnectionMethod, Provider


class OpenRouterProvider(Provider):
    def __init__(self, *, secret_prompt: Callable[[str], str]) -> None:
        self._secret_prompt = secret_prompt
        self._entry = get_auth_entry("openrouter")

    @property
    @override
    def id(self) -> str:
        return "openrouter"

    @property
    @override
    def display_name(self) -> str:
        return "OpenRouter"

    @property
    @override
    def docs_url(self) -> str | None:
        return "https://openrouter.ai/keys"

    @property
    @override
    def logo_url(self) -> str | None:
        return None

    @override
    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        return [
            APIKeyMethod(
                provider_id=self.id,
                secret_prompt=self._secret_prompt,
                validation_url=str(self._entry.validation_url)
                if self._entry.validation_url
                else None,
            ),
        ]
