from __future__ import annotations

import hashlib
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


def compute_fingerprint(secret: str) -> str:
    """Return a truncated SHA-256 fingerprint for change detection.

    The first 16 hex characters (64 bits) of the SHA-256 digest are enough to
    detect changes while remaining safe to store in non-secret metadata.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]
