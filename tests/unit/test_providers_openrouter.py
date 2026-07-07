from __future__ import annotations

import httpx
import pytest
from respx import MockRouter

from authlm.connection_methods.api_key import _default_secret_prompt
from authlm.credentials import ApiKeyCredential
from authlm.providers.openrouter import OpenRouterProvider
from authlm.validation import validate


def _provider() -> OpenRouterProvider:
    return OpenRouterProvider(secret_prompt=lambda _p: "sk-or-test")


def test_metadata() -> None:
    p = _provider()
    assert p.id == "openrouter"
    assert p.display_name == "OpenRouter"
    assert p.docs_url is not None
    assert "openrouter.ai" in p.docs_url


def test_only_api_key_method() -> None:
    p = _provider()
    methods = p.connection_methods(include_warned=False)
    assert len(methods) == 1
    assert methods[0].id == "api_key"
    assert methods[0].oauth_grant is None
    assert methods[0].warning is None


def test_openrouter_connection_methods_api_key_only() -> None:
    """OpenRouter exposes only api_key method, no OAuth."""
    provider = OpenRouterProvider(secret_prompt=_default_secret_prompt)
    methods = list(provider.connection_methods(include_warned=True))
    assert len(methods) == 1
    assert methods[0].id == "api_key"
    assert methods[0].oauth_grant is None
    assert methods[0].warning is None


@pytest.mark.asyncio
async def test_openrouter_validation_success(respx_mock: MockRouter) -> None:
    """OpenRouter validation probes the /auth/key endpoint."""
    respx_mock.get("https://openrouter.ai/api/v1/auth/key").mock(
        return_value=httpx.Response(200)
    )
    cred = ApiKeyCredential(
        provider="openrouter",
        alias="default",
        method_id="api_key",
        secret="sk-or-test",
    )
    result = await validate(cred, force=True)
    assert result is True


@pytest.mark.asyncio
async def test_openrouter_validation_failure(respx_mock: MockRouter) -> None:
    """OpenRouter validation returns False on 401."""
    respx_mock.get("https://openrouter.ai/api/v1/auth/key").mock(
        return_value=httpx.Response(401)
    )
    cred = ApiKeyCredential(
        provider="openrouter",
        alias="default",
        method_id="api_key",
        secret="sk-or-test",
    )
    result = await validate(cred, force=True)
    assert result is False
