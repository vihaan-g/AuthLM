from __future__ import annotations

from collections.abc import Sequence

from authlm.connection_methods.api_key import _default_secret_prompt
from authlm.errors import AuthLMError
from authlm.providers.base import ConnectionMethod, Provider

_PROVIDERS: Sequence[Provider] | None = None


def list_providers() -> Sequence[Provider]:
    """Return all registered providers."""
    global _PROVIDERS
    if _PROVIDERS is not None:
        return _PROVIDERS

    from authlm.providers.anthropic import AnthropicProvider
    from authlm.providers.google import GoogleProvider
    from authlm.providers.openai import OpenAIProvider
    from authlm.providers.openrouter import OpenRouterProvider

    _PROVIDERS = [
        OpenAIProvider(secret_prompt=_default_secret_prompt),
        AnthropicProvider(secret_prompt=_default_secret_prompt),
        GoogleProvider(secret_prompt=_default_secret_prompt),
        OpenRouterProvider(secret_prompt=_default_secret_prompt),
    ]
    return _PROVIDERS


def get_provider(provider_id: str) -> Provider:
    """Return a provider by ID.

    Args:
        provider_id: Stable provider identifier (e.g. ``"openai"``).

    Returns:
        The matching Provider instance.

    Raises:
        AuthLMError: No provider with the given ID is registered.
    """
    for provider in list_providers():
        if provider.id == provider_id:
            return provider
    raise AuthLMError(f"Unknown provider: {provider_id}")


def get_method(provider_id: str, method_id: str) -> ConnectionMethod:
    """Return a connection method by provider and method ID.

    Args:
        provider_id: Stable provider identifier (e.g. ``"openai"``).
        method_id: Method identifier (e.g. ``"api_key"``).

    Returns:
        The matching ConnectionMethod instance.

    Raises:
        AuthLMError: No provider or method matches the given IDs.
    """
    provider = get_provider(provider_id)
    for method in provider.connection_methods(include_warned=True):
        if method.id == method_id:
            return method
    raise AuthLMError(f"Unknown method {method_id!r} for provider {provider_id!r}")
