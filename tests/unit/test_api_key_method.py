from __future__ import annotations

from collections.abc import Iterator

import pytest

from authlm.connection_methods.api_key import APIKeyMethod
from authlm.credentials import ApiKeyCredential, Credential
from authlm.errors import AuthLMError


class _StubStore:
    def get(self, provider: str, alias: str) -> Credential | None:
        return None

    def set(self, credential: Credential) -> None:
        pass

    def delete(self, provider: str, alias: str) -> bool:
        return False

    def list(self) -> Iterator[tuple[str, str]]:
        return iter(())

    def backend_name(self) -> str:
        return "stub"


@pytest.fixture
def stub_store() -> _StubStore:
    return _StubStore()


def test_api_key_method_metadata() -> None:
    method = APIKeyMethod(provider_id="openai", secret_prompt=lambda _: "sk-test")

    assert method.id == "api_key"
    assert method.label == "Manually enter API key"
    assert method.warning is None
    assert method.oauth_grant is None


async def test_connect_returns_credential(stub_store: _StubStore) -> None:
    method = APIKeyMethod(provider_id="openai", secret_prompt=lambda _: "sk-test")

    cred = await method.connect(store=stub_store)

    assert isinstance(cred, ApiKeyCredential)
    assert cred.provider == "openai"
    assert cred.alias == "default"
    assert cred.method_id == "api_key"
    assert cred.secret == "sk-test"


async def test_connect_strips_whitespace(stub_store: _StubStore) -> None:
    method = APIKeyMethod(provider_id="openai", secret_prompt=lambda _: "  sk-test  \n")

    cred = await method.connect(store=stub_store)

    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


async def test_connect_rejects_empty(stub_store: _StubStore) -> None:
    method = APIKeyMethod(provider_id="openai", secret_prompt=lambda _: "   \n")

    with pytest.raises(AuthLMError):
        await method.connect(store=stub_store)
