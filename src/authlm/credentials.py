from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, Field, TypeAdapter


class Credential(BaseModel):
    provider: str
    alias: str
    method_id: str
    warning_acknowledged_at: datetime | None = None


class ApiKeyCredential(Credential):
    type: Literal["api_key"] = "api_key"
    secret: str


class OAuthCredential(Credential):
    type: Literal["oauth"] = "oauth"
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str] = Field(default_factory=list)
    client_id: str | None = None


CredentialUnion: TypeAlias = Annotated[
    ApiKeyCredential | OAuthCredential,
    Field(discriminator="type"),
]


_ADAPTER: TypeAdapter[ApiKeyCredential | OAuthCredential] = TypeAdapter(CredentialUnion)


def parse_credential(raw: str | bytes) -> Credential:
    """Deserialize a credential from JSON using the discriminated union."""
    return _ADAPTER.validate_json(raw)
