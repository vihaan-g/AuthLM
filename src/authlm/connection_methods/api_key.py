from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from typing_extensions import override

from authlm.credentials import ApiKeyCredential, Credential
from authlm.errors import AuthLMError
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores.base import CredentialStore


class _HttpGet(Protocol):
    async def __call__(self, url: str, *, headers: dict[str, str]) -> object: ...


def _default_secret_prompt(prompt: str) -> str:
    return input(prompt)


class APIKeyMethod(ConnectionMethod):
    def __init__(
        self,
        *,
        provider_id: str,
        secret_prompt: Callable[[str], str] = _default_secret_prompt,
        validation_url: str | None = None,
        http_get: _HttpGet | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._secret_prompt = secret_prompt
        self._validation_url = validation_url
        self._http_get = http_get

    def with_secret_prompt(self, prompt: Callable[[str], str]) -> APIKeyMethod:
        """Return a new instance with the given secret_prompt.

        Used by callers (especially the CLI) that need to inject a
        non-default prompt — e.g. Click's `prompt(hidden=True)`.
        """
        return APIKeyMethod(
            provider_id=self._provider_id,
            secret_prompt=prompt,
            validation_url=self._validation_url,
            http_get=self._http_get,
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

    @override
    async def validate(self, cred: Credential, *, force: bool) -> bool:
        if not isinstance(cred, ApiKeyCredential):
            return False
        if self._validation_url is None or self._http_get is None:
            return True
        headers = {"Authorization": f"Bearer {cred.secret}"}
        response = await self._http_get(self._validation_url, headers=headers)
        return 200 <= getattr(response, "status_code", 0) < 300
