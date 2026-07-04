from __future__ import annotations

from authlm.providers.base import OAuthGrant, Provider
from authlm.providers.registry import list_providers


def test_all_providers_satisfy_protocol() -> None:
    """All registered providers satisfy the Provider Protocol."""
    for provider in list_providers():
        assert isinstance(provider, Provider)


def test_oauth_grant_values() -> None:
    """OAuthGrant enum has expected values."""
    assert OAuthGrant.AUTHORIZATION_CODE_PKCE == "authorization_code_pkce"
    assert OAuthGrant.DEVICE_CODE == "device_code"
