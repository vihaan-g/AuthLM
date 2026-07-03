# Changelog

All notable changes to AuthLM are documented in this file.

The format is based on [Keep a Changelog 2.0.0](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-07

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
- Connection methods: `APIKeyMethod`, `OAuthPKCEMethod` (with loopback HTTP
  server), `OAuthDeviceCodeMethod` (with polling). All implement the
  `ConnectionMethod` Protocol.
- `models_dev` module: live fetch from `https://models.dev/api.json`,
  on-disk cache, and a vendored `_vendor/models-dev-snapshot.json`
  offline fallback.
- 4 built-in providers: `OpenAIProvider`, `AnthropicProvider` (with
  warned Claude Pro browser/headless methods),
  `GoogleProvider`, `OpenRouterProvider`.
- `providers.registry` with `list_providers`, `get_provider`, `get_method`.
- Public async API in `authlm.api`: `get_credential`,
  `get_valid_credential`, `refresh` (handles refresh-token rotation
  and classifies errors per spec §5.3), `should_refresh`, `connect`
  (orchestrates method + store + metadata), and `validate`.
- 5-command CLI in `authlm.cli` (Click group, entry point `authlm.cli:cli`):
  `connect` (interactive method picker with `[y/N]` warning confirmation for
  warned methods, refuses non-TTY without `--method`), `list` (ASCII table of
  stored credentials with backend and last-validated columns), `status`
  (per-credential metadata block; `--validate` probes the credential, `--force`
  allows probing warned methods, `--all` iterates aliases), `disconnect`
  (confirmation prompt; `--yes` to skip), `env` (exports credential as shell
  env vars in `shell` / `docker` / `github` formats; `eval "$(authlm env openai)"`
  for shell). The CLI is a thin sync wrapper: each command bridges to the
  async `authlm.api` functions via `asyncio.run()` per spec §2.3.
- Per-subcommand `--store` option mirrors the `AUTHLM_STORE` env
  var (one of `keyring`, `encrypted_file`, `env`, `memory`); `--metadata-path`
  mirrors `AUTHLM_METADATA_PATH`. Tests use `--store=memory` for isolation;
  users can use it to override the store on a per-invocation basis. The
  options live on each subcommand rather than the group, to avoid Click
  option-precedence ambiguity.
- `authlm.api.connect()` now accepts optional `on_prompt` and `open_browser`
  keyword-only parameters. When passed, they are propagated to the
  `OAuthDeviceCodeMethod` / `OAuthPKCEMethod` via new `with_on_prompt()` and
  `with_open_browser()` methods (mirroring the existing
  `APIKeyMethod.with_secret_prompt()`). Backward compatible: existing
  callers that omit these params see no change.
- `authlm.cli` is a subpackage (mirrors `connection_methods/` and
  `providers/`); `authlm.cli._context` provides `get_store()` and
  `is_tty()`; `authlm.cli._formatters` provides `format_list_table()` and
  `format_status_table()`.
- Dependabot bumps: `anthropic` 0.112.0 → 0.113.0 (PR #6), `astral-sh/setup-uv`
  SHA pin updated (PR #5).

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
- `validation.validate()` now runs the 4xx `TokenEndpointError` body
  through `redact_body` in `authlm.connection_methods._oauth_helpers`
  before including it in the exception message. `Bearer <token>` substrings
  and JSON-string fields named `access_token` / `refresh_token` /
  `id_token` / `client_secret` are replaced with `[REDACTED]`, and the
  body is truncated to 200 chars. Prevents credential leakage when OAuth
  providers echo tokens in error bodies (e.g. `invalid_token: <token>`).
  The `state` (CSRF) parameter is intentionally **not** redacted — it is
  not a credential and is useful for debugging.

### Changed
- Expanded README with status/build/license badges, a "Why AuthLM?" motivation
  section, a feature comparison table (vs `llm keys`, LiteLLM, provider SDKs),
  installation instructions (from source, since not yet on PyPI), CLI usage
  examples, a credential-stores reference table, and a security section
  linking to SECURITY.md. Corrected the broken `uv sync --extra test
  --all-extras` dev command to `uv sync --all-extras`.
- `authlm.plugins.DEFAULT_PLUGINS` now includes the 4 built-in provider
  modules, so `load_plugins()` registers them automatically.
- `scripts/refresh_models_dev.py` now uses `httpx` instead of `urllib` for
  HTTP requests (consistent with the library, sends a User-Agent header).
  Removed unused logo-fetching logic (no library code reads from
  `_vendor/_logos/`). Updated vendored snapshot with latest live data for
  the 4 built-in providers.
- `connect` (CLI) refuses to run with no `--method` on a non-TTY stdin and
  prints a clear error message; this avoids hangs in CI / scripts and matches
  the spec's "explicit over implicit" principle.
- The CLI sets `logging.getLogger("authlm").setLevel(logging.WARNING)` at
  startup so INFO-level logs from the OAuth methods (e.g. PKCE "Opening
  browser" info) do not pollute `eval $(authlm env ...)` stdout. The
  device-code URL and user code are routed to stderr via a custom `on_prompt`
  callback.
- `cli` group now uses `invoke_without_command=True` so `authlm` (no
  subcommand) prints help text and exits 0 instead of Click's default
  `MissingCommand` (exit 2). Implemented in commit `eab5f1f`.
- Updated v0.1.0 design spec (`.agents/specs/v0.1.0-authlm.md`) to reflect
  v0.1.0 reality: plugin system and models.dev integration removed from
  v0.1.0 scope (deferred to v0.2.0), `authlm status --backend` and
  `authlm.set_store()` added to v0.1.0 scope, `compute_fingerprint` wired
  into `MetadataEntry` for change detection, `Field(repr=False)` on all
  secret fields, `ProviderNotAvailable`/`AliasCollisionError` deferred to
  v0.2.0, `ConnectionMethod.validate()` removed from Protocol (validation
  goes through `validation.validate()` directly), roadmap replaced with
  4-version plan (v0.2.0 → v1.0.0).
- Created version spec outlines: `.agents/specs/v0.2.0-authlm.md`
  (Extensibility & Ecosystem), `.agents/specs/v0.3.0-authlm.md`
  (Robustness & More Stores), `.agents/specs/v1.0.0-authlm.md`
  (Stable Release).
- Updated `AGENTS.md` to reflect v0.1.0 reality (first-party providers
  only, no plugin system, `set_store()` in stores, `--backend` in status
  command, `Field(repr=False)` on secrets, version spec references).
- Updated `README.md` with honest v0.1.0 scope, roadmap section, and
  removed plugin system / models.dev from the features list.

### Deferred
- `OllamaProvider` (no-auth) is deferred to v0.2.0. See
  `.agents/specs/v0.2.0-authlm.md`.
- Plugin system (pluggy) is deferred to v0.2.0. See
  `.agents/specs/v0.2.0-authlm.md`.
- `models_dev` integration is deferred to v0.2.0. See
  `.agents/specs/v0.2.0-authlm.md`.
- `AwsCredential` / `AzureAdCredential` are deferred to v0.2.0. See
  `.agents/specs/v0.2.0-authlm.md`.
- `authlm import llm` / `authlm export` are deferred to v0.2.0. See
  `.agents/specs/v0.2.0-authlm.md`.
- File-locking (multi-process refresh safety) is deferred to v0.3.0. See
  `.agents/specs/v0.3.0-authlm.md`.
- Additional store backends (Vault, Bitwarden, 1Password) are deferred to
  v0.3.0. See `.agents/specs/v0.3.0-authlm.md`.

## [Unreleased]

### Added

### Fixed

### Changed

### Deferred

[Unreleased]: https://github.com/vihaan-g/AuthLM/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vihaan-g/AuthLM/releases/tag/v0.1.0
