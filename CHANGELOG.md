# Changelog

All notable changes to AuthLM are documented in this file.

The format is based on [Keep a Changelog 2.0.0](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding: `pyproject.toml` with hatchling build, ruff, mypy (strict),
  and pytest configuration.
- `authlm` package skeleton with `py.typed` marker and dynamic version sourced from
  `src/authlm/_version.py`.
- Core exception hierarchy in `authlm.errors` (`AuthLMError` and seven subclasses).
- Core credential types in `authlm.credentials` (Pydantic models: `ApiKeyCredential`,
  `OAuthCredential`) with a discriminated `CredentialUnion` over the v0.1.0 types.
  (Additional types `AwsCredential` and `AzureAdCredential` are defined in the spec
  for v0.2.0 but are not implemented in this release.)
- Test infrastructure: `tests/conftest.py` with environment isolation fixtures and a
  smoke test.
- `KeyringStore` in `authlm.stores.keyring_store`: OS keychain-backed credential store
  via the `keyring` library, with a JSON index file for enumeration (keyring has no
  enumeration API).
- `EncryptedFileStore` in `authlm.stores.encrypted_file_store`: Fernet-encrypted
  credential file store, with PBKDF2-HMAC key derivation from a passphrase.
- `get_default_store` in `authlm.stores`: auto-selects a `CredentialStore` from the
  `AUTHLM_STORE` env var (one of `keyring`, `encrypted_file`, `env`, `memory`),
  otherwise picks `KeyringStore` when a real keyring backend is available, and
  falls back to `EnvStore` with a warning when no keyring is present. Honors the
  `AUTHLM_USER_PATH` env var for the keyring index and encrypted file locations.
