from __future__ import annotations

from authlm._version import __version__ as __version__
from authlm.api import (
    connect,
    get_credential,
    get_valid_credential,
    refresh,
    should_refresh,
)
from authlm.credentials import (
    ApiKeyCredential,
    Credential,
    CredentialUnion,
    OAuthCredential,
    compute_fingerprint,
    parse_credential,
)
from authlm.errors import (
    AccessDenied,
    AuthLMError,
    ConnectionTimeout,
    CredentialNotFound,
    ReconnectionRequired,
    RefreshFailed,
    SecretStoreError,
    TokenEndpointError,
)
from authlm.providers.base import ConnectionMethod, OAuthGrant, Provider
from authlm.stores import (
    CredentialStore,
    EncryptedFileStore,
    EnvStore,
    KeyringStore,
    MemoryStore,
    get_default_store,
    set_store,
)
from authlm.validation import validate

__all__ = [
    "__version__",
    "connect",
    "get_credential",
    "get_valid_credential",
    "refresh",
    "should_refresh",
    "validate",
    "set_store",
    "get_default_store",
    "CredentialStore",
    "KeyringStore",
    "EncryptedFileStore",
    "EnvStore",
    "MemoryStore",
    "Credential",
    "ApiKeyCredential",
    "OAuthCredential",
    "CredentialUnion",
    "parse_credential",
    "compute_fingerprint",
    "Provider",
    "ConnectionMethod",
    "OAuthGrant",
    "AuthLMError",
    "ConnectionTimeout",
    "CredentialNotFound",
    "RefreshFailed",
    "ReconnectionRequired",
    "AccessDenied",
    "TokenEndpointError",
    "SecretStoreError",
]
