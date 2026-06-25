from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class AwsCredential(Credential):
    type: Literal["aws"] = "aws"
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None


class AzureAdCredential(Credential):
    type: Literal["azure_ad"] = "azure_ad"
    tenant_id: str
    client_id: str
    client_secret: str | None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
