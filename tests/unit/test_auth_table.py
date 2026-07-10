from __future__ import annotations

from urllib.parse import urlparse

import pytest
from pydantic import HttpUrl

from authlm._auth_table import (
    AUTH_TABLE,
    AuthTableEntry,
    OAuthConfig,
    get_auth_entry,
    get_oauth_config,
)


def test_oauth_config_fields() -> None:
    cfg = OAuthConfig(
        authorize_url=HttpUrl("https://auth.example.com/authorize"),
        token_url=HttpUrl("https://auth.example.com/token"),
        client_id="cid",
        default_scopes=["openid"],
    )
    assert str(cfg.authorize_url) == "https://auth.example.com/authorize"
    assert cfg.client_id == "cid"
    assert cfg.default_scopes == ["openid"]


def test_auth_table_entry_fields() -> None:
    entry = AuthTableEntry(
        provider_id="openai",
        oauth=OAuthConfig(
            authorize_url=HttpUrl("https://auth.example.com/authorize"),
            token_url=HttpUrl("https://auth.example.com/token"),
            client_id="cid",
            default_scopes=["openid"],
        ),
        validation_url=HttpUrl("https://api.example.com/v1/models"),
    )
    assert entry.provider_id == "openai"
    assert entry.oauth is not None


def test_auth_table_has_four_providers() -> None:
    assert set(AUTH_TABLE.keys()) == {"openai", "anthropic", "google", "openrouter"}


def test_openai_has_both_pkce_and_device() -> None:
    entry = get_auth_entry("openai")
    assert entry.oauth is not None
    assert entry.oauth.device_code_url is not None
    host = urlparse(str(entry.oauth.device_code_url)).hostname
    assert host is not None
    assert host in ("openai.com", "auth.openai.com")


def test_openai_default_client_id_is_codex_public() -> None:
    cfg = get_oauth_config("openai")
    assert cfg is not None
    assert cfg.client_id == "app_EMoamEEZ73f0CkXaXp7hrann"


def test_anthropic_default_client_id_is_claude_code_public() -> None:
    cfg = get_oauth_config("anthropic")
    assert cfg is not None
    assert cfg.client_id == "9d1c250a-e61b-44d9-88ed-5944d1962f5e"


def test_google_uses_pkce_only() -> None:
    entry = get_auth_entry("google")
    assert entry.oauth is not None
    assert entry.oauth.device_code_url is None


def test_openrouter_has_no_oauth() -> None:
    entry = get_auth_entry("openrouter")
    assert entry.oauth is None


def test_get_auth_entry_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_auth_entry("nonexistent")


def test_env_var_overrides_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTHLM_OPENAI_CLIENT_ID", "my-custom-id")
    cfg = get_oauth_config("openai")
    assert cfg is not None
    assert cfg.client_id == "my-custom-id"


def test_anthropic_loopback_port_set() -> None:
    cfg = get_oauth_config("anthropic")
    assert cfg is not None
    assert cfg.loopback_port == 5454


def test_openai_loopback_port_set() -> None:
    cfg = get_oauth_config("openai")
    assert cfg is not None
    assert cfg.loopback_port == 1455


def test_google_loopback_port_set() -> None:
    cfg = get_oauth_config("google")
    assert cfg is not None
    assert cfg.loopback_port == 8085


def test_google_extra_authorize_params_access_type_offline() -> None:
    """Google requires access_type=offline in authorize URL for refresh tokens."""
    cfg = get_oauth_config("google")
    assert cfg is not None
    assert cfg.extra_authorize_params == {"access_type": "offline"}


def test_google_validation_api_key_query_param_is_key() -> None:
    """Google API keys are validated via ?key= query param, not Bearer."""
    entry = get_auth_entry("google")
    assert entry.validation_api_key_query_param == "key"


def test_openai_validation_api_key_query_param_is_none() -> None:
    """OpenAI API keys use Bearer auth for validation (no query param)."""
    entry = get_auth_entry("openai")
    assert entry.validation_api_key_query_param is None


def test_openai_extra_authorize_params_include_codex_params() -> None:
    """OpenAI authorize URL includes Codex-specific params per reference impls."""
    cfg = get_oauth_config("openai")
    assert cfg is not None
    assert cfg.extra_authorize_params["codex_cli_simplified_flow"] == "true"
    assert cfg.extra_authorize_params["originator"] == "codex_cli_rs"
    assert cfg.extra_authorize_params["id_token_add_organizations"] == "true"


def test_openai_device_code_content_type_is_json() -> None:
    """OpenAI device-code endpoint expects JSON, not form-encoded."""
    cfg = get_oauth_config("openai")
    assert cfg is not None
    assert cfg.device_code_content_type == "application/json"


def test_anthropic_device_code_content_type_defaults_to_form_encoded() -> None:
    """Anthropic device-code endpoint uses form-encoded (the default)."""
    cfg = get_oauth_config("anthropic")
    assert cfg is not None
    assert cfg.device_code_content_type == "application/x-www-form-urlencoded"
