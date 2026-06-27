from __future__ import annotations

from collections.abc import Sequence

from authlm.errors import AuthLMError
from authlm.providers.base import ConnectionMethod, Provider


def _default_secret_prompt(prompt: str) -> str:
    return input(prompt)


def _build_providers() -> Sequence[Provider]:
    from authlm.providers.anthropic import AnthropicProvider
    from authlm.providers.google import GoogleProvider
    from authlm.providers.openai import OpenAIProvider
    from authlm.providers.openrouter import OpenRouterProvider

    return [
        OpenAIProvider(secret_prompt=_default_secret_prompt),
        AnthropicProvider(secret_prompt=_default_secret_prompt),
        GoogleProvider(secret_prompt=_default_secret_prompt),
        OpenRouterProvider(secret_prompt=_default_secret_prompt),
    ]


def list_providers() -> Sequence[Provider]:
    return _build_providers()


def get_provider(provider_id: str) -> Provider:
    for provider in list_providers():
        if provider.id == provider_id:
            return provider
    raise AuthLMError(f"Unknown provider: {provider_id}")


def get_method(provider_id: str, method_id: str) -> ConnectionMethod:
    provider = get_provider(provider_id)
    for method in provider.connection_methods(include_warned=True):
        if method.id == method_id:
            return method
    raise AuthLMError(f"Unknown method {method_id!r} for provider {provider_id!r}")
