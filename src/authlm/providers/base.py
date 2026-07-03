from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol, runtime_checkable

from authlm.credentials import Credential
from authlm.stores.base import CredentialStore


class OAuthGrant(StrEnum):
    """OAuth flow types supported by AuthLM connection methods."""

    AUTHORIZATION_CODE_PKCE = "authorization_code_pkce"
    DEVICE_CODE = "device_code"


@runtime_checkable
class ConnectionMethod(Protocol):
    """A specific way to authenticate to a provider."""

    @property
    def id(self) -> str:
        """Unique within the provider, e.g. 'api_key'."""
        ...

    @property
    def label(self) -> str:
        """What the user sees in the CLI."""
        ...

    @property
    def warning(self) -> str | None:
        """If non-None, printed before connect; user must confirm."""
        ...

    @property
    def oauth_grant(self) -> OAuthGrant | None:
        """None for non-OAuth methods; OAuthGrant enum for OAuth flows."""
        ...

    async def connect(self, *, store: CredentialStore) -> Credential:
        """Run the auth flow interactively; persist the result; return it."""
        ...

    async def validate(self, cred: Credential, *, force: bool) -> bool:
        """Probe whether the credential is currently usable."""
        ...


@runtime_checkable
class Provider(Protocol):
    """Identifies an AI service and its supported connection methods."""

    @property
    def id(self) -> str:
        """Stable identifier, e.g. 'openai'."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name, e.g. 'OpenAI'."""
        ...

    @property
    def docs_url(self) -> str | None:
        """Link to the provider's API key signup page."""
        ...

    def connection_methods(self, *, include_warned: bool) -> Sequence[ConnectionMethod]:
        """Return connection methods. Exclude warned unless include_warned."""
        ...
