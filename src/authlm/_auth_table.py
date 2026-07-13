from __future__ import annotations

import os

from pydantic import BaseModel, Field, HttpUrl

_ENV_CLIENT_ID = {
    "openai": "AUTHLM_OPENAI_CLIENT_ID",
    "anthropic": "AUTHLM_ANTHROPIC_CLIENT_ID",
    "google": "AUTHLM_GOOGLE_CLIENT_ID",
}
_DEFAULT_CLIENT_ID = {
    "openai": "app_EMoamEEZ73f0CkXaXp7hrann",
    "anthropic": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
    "google": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",  # noqa: E501
}


class OAuthConfig(BaseModel):
    authorize_url: HttpUrl
    token_url: HttpUrl
    device_code_url: HttpUrl | None = None
    device_code_poll_url: HttpUrl | None = None
    device_code_verification_uri: HttpUrl | None = None
    device_code_redirect_uri: HttpUrl | None = None
    client_id: str
    default_scopes: list[str] = Field(default_factory=list)
    loopback_port: int | None = None
    fixed_redirect_uri: HttpUrl | None = None
    extra_authorize_params: dict[str, str] = Field(default_factory=dict)
    device_code_content_type: str = "application/x-www-form-urlencoded"


class AuthTableEntry(BaseModel):
    provider_id: str
    oauth: OAuthConfig | None = None
    validation_url: HttpUrl | None = None
    validation_api_key_query_param: str | None = None


AUTH_TABLE: dict[str, AuthTableEntry] = {
    "openai": AuthTableEntry(
        provider_id="openai",
        oauth=OAuthConfig(
            authorize_url=HttpUrl("https://auth.openai.com/oauth/authorize"),
            token_url=HttpUrl("https://auth.openai.com/oauth/token"),
            device_code_url=HttpUrl(
                "https://auth.openai.com/api/accounts/deviceauth/usercode"
            ),
            device_code_poll_url=HttpUrl(
                "https://auth.openai.com/api/accounts/deviceauth/token"
            ),
            device_code_verification_uri=HttpUrl(
                "https://auth.openai.com/codex/device"
            ),
            device_code_redirect_uri=HttpUrl(
                "https://auth.openai.com/deviceauth/callback"
            ),
            client_id=_DEFAULT_CLIENT_ID["openai"],
            default_scopes=["openid", "profile", "email", "offline_access"],
            loopback_port=1455,
            fixed_redirect_uri=HttpUrl("http://localhost:1455/auth/callback"),
            extra_authorize_params={
                "codex_cli_simplified_flow": "true",
                "originator": "codex_cli_rs",
                "id_token_add_organizations": "true",
            },
            device_code_content_type="application/json",
        ),
        validation_url=HttpUrl("https://api.openai.com/v1/models"),
    ),
    "anthropic": AuthTableEntry(
        provider_id="anthropic",
        oauth=OAuthConfig(
            authorize_url=HttpUrl("https://claude.ai/oauth/authorize"),
            token_url=HttpUrl("https://console.anthropic.com/v1/oauth/token"),
            device_code_url=HttpUrl(
                "https://console.anthropic.com/v1/oauth/device/code"
            ),
            client_id=_DEFAULT_CLIENT_ID["anthropic"],
            default_scopes=[
                "org:create_api_key",
                "user:profile",
                "user:inference",
            ],
            loopback_port=5454,
        ),
        validation_url=HttpUrl("https://api.anthropic.com/v1/models"),
    ),
    "google": AuthTableEntry(
        provider_id="google",
        oauth=OAuthConfig(
            authorize_url=HttpUrl("https://accounts.google.com/o/oauth2/v2/auth"),
            token_url=HttpUrl("https://oauth2.googleapis.com/token"),
            client_id=_DEFAULT_CLIENT_ID["google"],
            default_scopes=[
                "openid",
                "https://www.googleapis.com/auth/generative-language.retriever",
            ],
            loopback_port=8085,
            extra_authorize_params={"access_type": "offline"},
        ),
        validation_url=HttpUrl(
            "https://generativelanguage.googleapis.com/v1beta/models"
        ),
        validation_api_key_query_param="key",
    ),
    "openrouter": AuthTableEntry(
        provider_id="openrouter",
        validation_url=HttpUrl("https://openrouter.ai/api/v1/auth/key"),
    ),
}


def get_auth_entry(provider_id: str) -> AuthTableEntry:
    """Return the full AuthTableEntry for a provider.

    Returns the complete auth configuration including OAuth endpoints,
    client IDs, validation URLs, and key issuance URLs. For OAuth-specific
    configuration with env-var client ID overrides resolved, use
    :func:`get_oauth_config` instead.

    Args:
        provider_id: Provider ID (e.g. ``"openai"``, ``"anthropic"``).

    Returns:
        AuthTableEntry for the provider.

    Raises:
        KeyError: Unknown provider (surfaced as AuthLMError by callers).
    """
    return AUTH_TABLE[provider_id]


def get_oauth_config(provider_id: str) -> OAuthConfig | None:
    cfg = AUTH_TABLE[provider_id].oauth
    if cfg is None:
        return None
    default_id = _DEFAULT_CLIENT_ID.get(provider_id)
    if default_id is None:
        return cfg
    env_var = _ENV_CLIENT_ID.get(provider_id)
    resolved: str = default_id
    if env_var is not None:
        override = os.environ.get(env_var)
        if override:
            resolved = override
    if resolved == cfg.client_id:
        return cfg
    return cfg.model_copy(update={"client_id": resolved})


def is_default_client_id(provider_id: str, client_id: str) -> bool:
    """Return True if client_id matches the hardcoded default for the provider."""
    return client_id == _DEFAULT_CLIENT_ID.get(provider_id)
