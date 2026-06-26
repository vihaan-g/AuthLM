from __future__ import annotations

from collections.abc import Sequence

from authlm.credentials import Credential
from authlm.providers.base import (
    ConnectionMethod,
    OAuthGrant,
    Provider,
)
from authlm.stores.base import CredentialStore


class _FakeMethod:
    @property
    def id(self) -> str:
        return "api_key"

    @property
    def label(self) -> str:
        return "API Key"

    @property
    def warning(self) -> str | None:
        return None

    @property
    def oauth_grant(self) -> OAuthGrant | None:
        return None

    async def connect(self, *, store: CredentialStore) -> Credential:
        raise NotImplementedError

    async def validate(self, cred: Credential, *, force: bool) -> bool:
        return True


class _FakeProvider:
    @property
    def id(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI"

    @property
    def docs_url(self) -> str | None:
        return "https://platform.openai.com/api-keys"

    @property
    def logo_url(self) -> str | None:
        return None

    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        return [_FakeMethod()]


def test_oauth_grant_values() -> None:
    assert OAuthGrant.AUTHORIZATION_CODE_PKCE == "authorization_code_pkce"
    assert OAuthGrant.DEVICE_CODE == "device_code"


def test_fake_method_satisfies_protocol() -> None:
    assert isinstance(_FakeMethod(), ConnectionMethod)


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(_FakeProvider(), Provider)


def test_provider_connection_methods() -> None:
    provider = _FakeProvider()
    methods = provider.connection_methods(include_warned=False)
    assert len(methods) == 1
    assert methods[0].id == "api_key"
