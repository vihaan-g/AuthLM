from __future__ import annotations

import sys
from pathlib import Path

import pytest

from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.errors import AuthLMError
from authlm.stores.base import CredentialStore
from authlm.stores.encrypted_file_store import EncryptedFileStore


def _api_key() -> ApiKeyCredential:
    return ApiKeyCredential(
        provider="openai", alias="default", method_id="api_key", secret="sk-test"
    )


def _oauth() -> OAuthCredential:
    return OAuthCredential(
        provider="anthropic",
        alias="work",
        method_id="m",
        access_token="a",
        refresh_token="r",
        expires_at=None,
    )


def _store(tmp_path: Path, passphrase: str = "correct") -> EncryptedFileStore:
    return EncryptedFileStore(
        path=tmp_path / "creds.enc.json",
        passphrase=passphrase,
        iterations=1000,
    )


def test_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(_store(tmp_path), CredentialStore)


def test_set_and_get(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert _store(tmp_path).get("openai", "default") is None


def test_set_overwrites(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-new"
        )
    )
    cred = store.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-new"


def test_delete_existing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    assert store.delete("openai", "default") is True
    assert store.get("openai", "default") is None


def test_delete_missing_returns_false(tmp_path: Path) -> None:
    assert _store(tmp_path).delete("openai", "default") is False


def test_list(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    store.set(_oauth())
    pairs = sorted(store.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_wrong_passphrase_raises(tmp_path: Path) -> None:
    store1 = _store(tmp_path, passphrase="correct")
    store1.set(_api_key())
    store2 = _store(tmp_path, passphrase="wrong")
    with pytest.raises(AuthLMError):
        store2.get("openai", "default")


def test_list_works_without_passphrase(tmp_path: Path) -> None:
    store1 = _store(tmp_path, passphrase="correct")
    store1.set(_api_key())
    store1.set(_oauth())
    store2 = _store(tmp_path, passphrase="wrong")
    pairs = sorted(store2.list())
    assert pairs == [("anthropic", "work"), ("openai", "default")]


def test_backend_name(tmp_path: Path) -> None:
    assert _store(tmp_path).backend_name() == "Encrypted File"


def test_persists_across_instances(tmp_path: Path) -> None:
    store1 = _store(tmp_path)
    store1.set(_api_key())
    store2 = _store(tmp_path)
    cred = store2.get("openai", "default")
    assert cred is not None
    assert isinstance(cred, ApiKeyCredential)
    assert cred.secret == "sk-test"


def test_atomic_write_no_temp_file_left(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    path = tmp_path / "creds.enc.json"
    assert path.exists()
    assert not (tmp_path / "creds.enc.json.tmp").exists()


def test_file_permissions_owner_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set(_api_key())
    path = tmp_path / "creds.enc.json"
    if sys.platform == "win32":
        _assert_windows_owner_only(path)
    else:
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600


def _assert_windows_owner_only(path: Path) -> None:
    """Verify the file DACL grants access only to the current user."""
    import win32security  # type: ignore[import-untyped]

    security = win32security.GetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = security.GetSecurityDescriptorDacl()
    assert dacl is not None, "File has no DACL"

    everyone_sid, _, _ = win32security.LookupAccountName(None, "Everyone")
    users_sid, _, _ = win32security.LookupAccountName(None, "BUILTIN\\Users")
    admin_sid, _, _ = win32security.LookupAccountName(None, "BUILTIN\\Administrators")

    allowed_sids: set[object] = set()
    for index in range(dacl.GetAceCount()):
        # pywin32 ACL.GetAce return shape varies by build:
        # 3 values (e.g. build 312): (AceType, AccessMask, Sid)
        # 4 values: (AceType, AceFlags, AccessMask, Sid)
        # 5 values (newer): (AceType, AceFlags, AccessMask, SidType, Sid)
        # The SID is always the last element, regardless of version.
        allowed_sids.add(dacl.GetAce(index)[-1])

    assert everyone_sid not in allowed_sids, "Everyone has access"
    assert users_sid not in allowed_sids, "BUILTIN\\Users has access"
    assert admin_sid not in allowed_sids, (
        "BUILTIN\\Administrators should not be granted access"
    )
    current_user = win32security.LookupAccountName(None, _current_username())[0]
    assert current_user in allowed_sids, "Current user is missing from DACL"


def _current_username() -> str:
    import getpass

    return getpass.getuser()
