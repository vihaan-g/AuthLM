from __future__ import annotations

import base64
import getpass
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field
from typing_extensions import override

from authlm.credentials import Credential, parse_credential
from authlm.errors import SecretStoreError
from authlm.stores.base import CredentialStore


class _EncryptedFile(BaseModel):
    salt: str | None = None
    iterations: int
    entries: dict[str, str] = Field(default_factory=dict)


def _derive_fernet_key(passphrase: bytes, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase))


def _restrict_permissions(path: Path) -> None:
    """Restrict file permissions to owner-only (0o600 on POSIX, ACL on Windows)."""
    if sys.platform == "win32":
        _restrict_permissions_windows(path)
    else:
        os.chmod(path, 0o600)


def _restrict_permissions_windows(path: Path) -> None:
    """Restrict file permissions to current user via NTFS ACLs.

    Removes inherited ACEs (equivalent to ``icacls /inheritance:r``) and replaces
    the DACL with a single Read+Write ACE for the current user (equivalent to
    ``icacls /grant:r "<user>:(R,W)"``). The ``pywin32`` package is a
    platform-marked core dependency on Windows, so the import is safe.
    """
    import ntsecuritycon  # type: ignore[import-untyped]  # pyright: ignore[reportMissingModuleSource]
    import win32security  # type: ignore[import-untyped]  # pyright: ignore[reportMissingModuleSource]

    user_sid, _, _ = win32security.LookupAccountName(None, getpass.getuser())
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        ntsecuritycon.FILE_GENERIC_READ | ntsecuritycon.FILE_GENERIC_WRITE,
        user_sid,
    )
    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION
        | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        dacl,
        None,
    )


class EncryptedFileStore(CredentialStore):
    """Fernet-encrypted credential file store."""

    def __init__(
        self,
        *,
        path: Path,
        passphrase: str,
        iterations: int,
    ) -> None:
        self._path = path
        self._passphrase = passphrase
        self._iterations = iterations

    @override
    def get(self, provider: str, alias: str) -> Credential | None:
        file = self._read()
        if file.salt is None:
            return None
        token = file.entries.get(f"{provider}:{alias}")
        if token is None:
            return None
        fernet = self._fernet(file.salt, file.iterations)
        try:
            raw = fernet.decrypt(token)
        except InvalidToken:
            raise SecretStoreError("Credential store is locked or corrupted") from None
        return parse_credential(raw)

    @override
    def set(self, credential: Credential) -> None:
        file = self._read()
        if file.salt is None:
            file.salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
            file.iterations = self._iterations
        fernet = self._fernet(file.salt, file.iterations)
        key = f"{credential.provider}:{credential.alias}"
        file.entries[key] = fernet.encrypt(
            credential.model_dump_json().encode()
        ).decode()
        self._write(file)

    @override
    def delete(self, provider: str, alias: str) -> bool:
        file = self._read()
        key = f"{provider}:{alias}"
        if key not in file.entries:
            return False
        del file.entries[key]
        self._write(file)
        return True

    @override
    def list(self) -> Iterator[tuple[str, str]]:
        file = self._read()
        for key in file.entries:
            provider, _, alias = key.partition(":")
            yield (provider, alias)

    @override
    def backend_name(self) -> str:
        return "Encrypted File"

    def _fernet(self, salt_b64: str, iterations: int) -> Fernet:
        salt = base64.urlsafe_b64decode(salt_b64)
        key = _derive_fernet_key(self._passphrase.encode(), salt, iterations)
        return Fernet(key)

    def _read(self) -> _EncryptedFile:
        if not self._path.exists():
            return _EncryptedFile(iterations=self._iterations)
        data = json.loads(self._path.read_text())
        return _EncryptedFile.model_validate(data)

    def _write(self, file: _EncryptedFile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(file.model_dump_json(indent=2))
        _restrict_permissions(tmp_path)
        os.replace(tmp_path, self._path)
