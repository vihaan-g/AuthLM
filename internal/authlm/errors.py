from __future__ import annotations


class AuthLMError(Exception):
    """Base for all AuthLM exceptions."""


class CredentialNotFound(AuthLMError):
    """No credential stored for the given (provider, alias)."""


class RefreshFailed(AuthLMError):
    """Transient network error or 5xx from token endpoint. Retry with backoff."""


class ReconnectionRequired(AuthLMError):
    """Refresh token is dead (invalid_grant). User must re-run connect()."""


class AccessDenied(AuthLMError):
    """Token works but user lacks access (403 entitlement_denied)."""


class TokenEndpointError(AuthLMError):
    """Other 4xx from token endpoint. Surface provider's error message."""


class ProviderNotAvailable(AuthLMError):
    """Provider SDK not installed. Message includes install hint."""


class AliasCollisionError(AuthLMError):
    """Two plugins registered the same (provider, alias)."""
