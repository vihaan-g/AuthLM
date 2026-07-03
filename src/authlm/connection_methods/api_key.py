from __future__ import annotations

from collections.abc import Callable

from typing_extensions import override

from authlm.credentials import ApiKeyCredential, Credential
from authlm.errors import AuthLMError
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores.base import CredentialStore


def _default_secret_prompt(prompt: str) -> str:
    return input(prompt)


class APIKeyMethod(ConnectionMethod):
    def __init__(
        self,
        *,
        provider_id: str,
        secret_prompt: Callable[[str], str] = _default_secret_prompt,
    ) -> None:
        self._provider_id = provider_id
        self._secret_prompt = secret_prompt

    def with_secret_prompt(self, prompt: Callable[[str], str]) -> APIKeyMethod:
        """Return a new instance with the given secret_prompt.

        Used by callers (especially the CLI) that need to inject a
        non-default prompt — e.g. Click's `prompt(hidden=True)`.
        """
        return APIKeyMethod(
            provider_id=self._provider_id,
            secret_prompt=prompt,
        )

    @property
    @override
    def id(self) -> str:
        return "api_key"

    @property
    @override
    def label(self) -> str:
        return "Manually enter API key"

    @property
    @override
    def warning(self) -> str | None:
        return None

    @property
    @override
    def oauth_grant(self) -> OAuthGrant | None:
        return None

    @override
    async def connect(self, *, store: CredentialStore) -> Credential:
        secret = self._secret_prompt(f"Enter {self._provider_id} API key: ").strip()
        if not secret:
            raise AuthLMError("API key is empty; cannot connect.")
        return ApiKeyCredential(
            provider=self._provider_id,
            alias="default",
            method_id=self.id,
            secret=secret,
        )
