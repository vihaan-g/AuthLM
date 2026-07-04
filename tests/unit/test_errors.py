from __future__ import annotations

import pytest

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

SUBCLASSES: list[type[AuthLMError]] = [
    CredentialNotFound,
    RefreshFailed,
    ReconnectionRequired,
    AccessDenied,
    TokenEndpointError,
    SecretStoreError,
    ConnectionTimeout,
]


def test_authlm_error_is_exception() -> None:
    assert issubclass(AuthLMError, Exception)


def test_subclasses_inherit_authlm_error() -> None:
    for exc in SUBCLASSES:
        assert issubclass(exc, AuthLMError)


@pytest.mark.parametrize("exc", SUBCLASSES)
def test_can_raise_and_catch_as_base(exc: type[AuthLMError]) -> None:
    with pytest.raises(AuthLMError):
        raise exc("message")


def test_message_round_trips() -> None:
    assert str(CredentialNotFound("missing")) == "missing"
