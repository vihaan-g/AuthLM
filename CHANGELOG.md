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
- `parse_credential()` deserialization helper in `authlm.credentials` (uses the
  discriminated union to restore the correct subclass from JSON).
- `compute_fingerprint(secret)` in `authlm.credentials` returning a truncated
  SHA-256 digest for non-secret change detection.
  (Additional types `AwsCredential` and `AzureAdCredential` are defined in the spec
  for v0.2.0 but are not implemented in this release.)
- Test infrastructure: `tests/conftest.py` with environment isolation fixtures and a
  smoke test.
- `MemoryStore` in `authlm.stores.memory_store`: in-process credential store for
  tests, cleared on process exit.
- `EnvStore` in `authlm.stores.env_store`: read-only store that reads API keys
  from environment variables (module-level `_ENV_VAR_MAP` covers v0.1.0
  providers: `openai`, `anthropic`, `google`, `openrouter`).
- `KeyringStore` in `authlm.stores.keyring_store`: OS keychain-backed credential store
  via the `keyring` library, with a JSON index file for enumeration (keyring has no
  enumeration API).
- Plugin loader in `authlm.plugins`: idempotent `pluggy.PluginManager` singleton
  (`load_plugins` / `get_plugin_manager`) that registers hookspecs, skips
  setuptools entry-point discovery under `sys._called_from_test`, and tolerates
  broken `DEFAULT_PLUGINS` modules by logging a warning.
- `EncryptedFileStore` in `authlm.stores.encrypted_file_store`: Fernet-encrypted
  credential file store, with PBKDF2-HMAC key derivation from a passphrase.
- `get_default_store` in `authlm.stores`: auto-selects a `CredentialStore` from the
  `AUTHLM_STORE` env var (one of `keyring`, `encrypted_file`, `env`, `memory`),
  otherwise picks `KeyringStore` when a real keyring backend is available, and
  falls back to `EnvStore` with a warning when no keyring is present. Honors the
  `AUTHLM_USER_PATH` env var for the keyring index and encrypted file locations.
- `Provider` and `ConnectionMethod` Protocols in `authlm.providers.base`, plus the
  `OAuthGrant` `StrEnum` enumerating supported OAuth flow types
  (`authorization_code_pkce`, `device_code`). Both Protocols are
  `@runtime_checkable` for `isinstance()` tests; no implementations are included
  in v0.1.0 yet.
- pluggy hookspecs in `authlm.hookspecs` defining `register_providers`,
  `register_connection_methods`, and `register_stores` hooks for third-party
  plugin registration of providers, connection methods, and credential store
  backends, plus an exported `hookimpl` marker for plugin authors.
- `authlm._auth_table` with v0.1.0 provider auth metadata: `OAuthConfig` and
  `AuthTableEntry` Pydantic models, an `AUTH_TABLE` covering `openai`,
  `anthropic`, `google`, and `openrouter` (with public OAuth client IDs and
  PKCE/device endpoints for the three OAuth-capable providers), and
  `get_auth_entry` / `get_oauth_config` lookups. Client IDs are overridable
  per provider via `AUTHLM_{OPENAI,ANTHROPIC,GOOGLE}_CLIENT_ID` env vars.
- `authlm.validation.validate()` async probe that GETs each provider's
  `validation_url` from `_auth_table` (OpenAI `/v1/models`, Anthropic
  `/v1/models` with `x-api-key` + `anthropic-version` headers, etc.) and
  returns `True` on 2xx, `False` on 401/404, raises `AccessDenied` on 403
  entitlement denial, and `TokenEndpointError` on other 4xx. Refuses warned
  subscription methods (`claude_pro_oauth_browser`,
  `claude_pro_oauth_device`) unless `force=True` is passed, and is
  no-op-detectable for providers without a `validation_url`.

### Fixed
- `EncryptedFileStore` file permissions now work on Windows: replaced the
  POSIX-only `os.chmod(0o600)` with a platform-aware `_restrict_permissions`
  that uses `pywin32` (`SetNamedSecurityInfo` with
  `PROTECTED_DACL_SECURITY_INFORMATION`) on Windows to strip inherited ACLs
  and grant Read+Write only to the current user. `pywin32>=307` is a
  platform-marked core dependency (`sys_platform == 'win32'`).
- Keyring store and encrypted file store now wrap raw backend errors
  (`keyring.errors.*`, file I/O) in `SecretStoreError` so consumers can
  catch all secret-store failures with a single `AuthLMError` subclass.
- `get_default_store` now emits a `WARNING`-level log when the encrypted
  file passphrase is sourced from `AUTHLM_PASSPHRASE` (visible to child
  processes and `/proc/<pid>/environ` on Linux); prefer an interactive
  prompt.

### Changed
- Expanded README with status/build/license badges, a "Why AuthLM?" motivation
  section, a feature comparison table (vs `llm keys`, LiteLLM, provider SDKs),
  installation instructions (from source, since not yet on PyPI), CLI usage
  examples, a credential-stores reference table, and a security section
  linking to SECURITY.md. Corrected the broken `uv sync --extra test
  --all-extras` dev command to `uv sync --all-extras`.
