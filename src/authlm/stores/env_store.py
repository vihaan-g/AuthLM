from __future__ import annotations

import os
from collections.abc import Iterator, Mapping

from typing_extensions import override

from authlm.credentials import ApiKeyCredential, Credential
from authlm.errors import CredentialNotFound, SecretStoreError
from authlm.stores.base import CredentialStore

_ENV_VAR_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class EnvStore(CredentialStore):
    """Read-only store that reads API keys from environment variables."""

    def __init__(self, *, mapping: Mapping[str, str]) -> None:
        self._mapping = dict(mapping)

    @override
    def get(self, provider: str, alias: str) -> Credential | None:
        if alias != "default":
            raise CredentialNotFound(
                f"EnvStore only supports alias='default', got {alias!r}"
            )
        env_var = self._mapping.get(provider)
        if env_var is None:
            return None
        secret = os.environ.get(env_var)
        if secret is None:
            return None
        return ApiKeyCredential(
            provider=provider,
            alias="default",
            method_id="env",
            secret=secret,
        )

    @override
    def set(self, credential: Credential) -> None:
        raise SecretStoreError(
            "EnvStore is read-only; set environment variables instead"
        )

    @override
    def delete(self, provider: str, alias: str) -> bool:
        raise SecretStoreError(
            "EnvStore is read-only; unset the environment variable instead"
        )

    @override
    def list(self) -> Iterator[tuple[str, str]]:
        for provider, env_var in self._mapping.items():
            if os.environ.get(env_var) is not None:
                yield (provider, "default")

    @override
    def backend_name(self) -> str:
        return "Environment"
