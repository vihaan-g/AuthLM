# AGENTS.md

AuthLM is a Python library for managing authentication and credentials for AI providers (OpenAI, Anthropic, Google, etc.). Auth-only — it does not do inference. Apache-2.0. Full design: `.agents/specs/v0.1.0-authlm.md`. Version roadmap: `.agents/specs/v0.2.0-authlm.md` through `v1.0.0-authlm.md`.

## Project Structure

- `src/authlm/` — the library source (src layout)
  - `__init__.py` — public API re-exports (`connect`, `get_credential`, `get_valid_credential`, `refresh`, `should_refresh`, `validate`, `set_store`, credential types, errors, stores).
  - `api.py` — public async API: `get_credential`, `get_valid_credential`, `refresh`, `should_refresh`, `connect`, `validate`. All 6 are `async` (including `get_credential`, which has no I/O — deliberate design choice per spec §2.3 for API consistency).
  - `credentials.py` — Pydantic Credential types for v0.1.0: `ApiKeyCredential`, `OAuthCredential`, plus `CredentialUnion` discriminated union, `parse_credential()`, and `compute_fingerprint()`. Secret fields use `Field(repr=False)`. Additional types (`AwsCredential`, `AzureAdCredential`) are deferred to v0.2.0.
  - `metadata.py` — `MetadataEntry` Pydantic model (includes `fingerprint` for change detection) and `MetadataStore` for non-secret credential metadata.
  - `validation.py` — `validate()` async probe of a credential against the provider's `validation_url`; refuses warned methods (Anthropic Claude Pro) unless `force=True`. `validate()` raises `PermissionError` (built-in) for warned-method refusal; callers that want to catch this alongside other authlm errors use `except (AuthLMError, PermissionError)`.
  - `_auth_table.py` — Pydantic `OAuthConfig` and `AuthTableEntry` models, plus a static `AUTH_TABLE` dict covering the 4 built-in providers. `OAuthConfig` carries `extra_authorize_params`, `device_code_content_type`, and per-provider OAuth client IDs (overridable via env vars). `AuthTableEntry` carries `validation_url` and `validation_api_key_query_param` for credential probes. Also exports `get_auth_entry`, `get_oauth_config`, and `is_default_client_id`.
  - `providers/` — 4 built-in providers for v0.1.0: `openai` (api_key, oauth_browser, oauth_device), `anthropic` (api_key + 2 warned Claude Pro methods), `google` (api_key, oauth_browser), `openrouter` (api_key). First-party only — no plugin system in v0.1.0. Plus `base.py` (Protocols) and `registry.py` (`get_provider`, `list_providers`, `get_method`).
  - `connection_methods/` — `api_key.py` (APIKeyMethod), `oauth_pkce.py` (OAuthPKCEMethod with loopback HTTP server), `oauth_device.py` (OAuthDeviceCodeMethod with polling), `_oauth_helpers.py` (PKCE generation, URL redaction, token-endpoint error classification, body redaction), `__init__.py` re-exports.
  - `stores/` — `base.py` (`CredentialStore` Protocol), `memory_store.py`, `env_store.py`, `keyring_store.py`, `encrypted_file_store.py`, `__init__.py` (`get_default_store` auto-selection, `set_store` programmatic override).
  - `cli/` — Click CLI subpackage, entry point `authlm.cli:cli` (`[project.scripts]` in `pyproject.toml`):
    - `__init__.py` — `cli` Click group; registers the 5 subcommands; sets `logging.getLogger("authlm").setLevel(logging.WARNING)` at startup so OAuth INFO logs don't pollute `eval $(authlm env ...)` stdout. Uses `invoke_without_command=True` so `authlm` (no subcommand) prints help.
    - `_context.py` — `get_metadata_path(override)` resolver (chains explicit override → `AUTHLM_METADATA_PATH` → `AUTHLM_USER_PATH` → `get_user_data_path()`).
    - `_formatters.py` — pure string functions `format_list_table` and `format_status_table` for the `list` and `status` commands.
    - `connect.py` — `authlm connect` command: provider lookup, method picker (interactive or `--method`), warned-method filtering (`--include-warned`), `[y/N]` confirmation, Google OAuth pre-flight warning when default client ID is in use, Click-aware secret/device-code/browser callbacks, non-TTY refusal per spec §2.3.
    - `list_cmd.py` — `authlm list` command: ASCII table of stored credentials.
    - `status.py` — `authlm status` command: per-credential metadata block, `--backend` / `--validate` / `--force` / `--all` flags.
    - `disconnect.py` — `authlm disconnect` command: `[y/N]` confirmation, `--yes` to skip.
    - `env.py` — `authlm env` command: exports credential as `KEY=VALUE` lines in `shell` / `docker` / `github` formats.
  - `errors.py` — exception hierarchy (`AuthLMError` base + `SecretStoreError`, `CredentialNotFound`, `RefreshFailed`, `ReconnectionRequired`, `AccessDenied`, `TokenEndpointError`). `ProviderNotAvailable` and `AliasCollisionError` are deferred to v0.2.0 (plugin system).
- `tests/` — `unit/`, `integration/` (v0.2.0), `security/` (v0.2.0), `cassettes/` (VCR.py, v0.2.0)
- `.agents/specs/` — design specs per version: `v0.1.0-authlm.md` (full spec), `v0.2.0-authlm.md` through `v1.0.0-authlm.md` (outlines). Read before architectural work.
- `.agents/rules/general.md` — project-wide coding rules (read before any coding)
- `SECURITY.md` — threat model, reporting a vulnerability, supported backends.
- `CONTRIBUTING.md` — contributor guide.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.0.

## Setup

- Requires Python 3.11+.
- Install uv first: `pip install uv` (or use `brew install uv`).
- Sync deps: `uv sync --all-extras`
- Activate: `source .venv/bin/activate` (or use `uv run <cmd>`)

## Commands

- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .` — run after changes
- **Typecheck:** `uv run mypy src/authlm` — must pass with `--strict`
- **Test (focused):** `uv run pytest tests/unit/<area>` — run for the area you changed
- **Test (full):** `uv run pytest` — currently 314 unit tests, under 10 seconds; run freely
- **Build:** `uv run python -m build`
- **CLI smoke test:** `uv run authlm --help` — should list all 5 subcommands (`connect`, `list`, `status`, `disconnect`, `env`).

### When to verify

While iterating, run targeted checks on just the file(s) you're touching rather than the full gate:

- Typecheck a single file: `uv run mypy src/authlm/path/to/file.py`
- Run a single test: `uv run pytest tests/unit/path/to/test_file.py::test_name`

Reserve the full `ruff check . && ruff format . && mypy src/authlm && pytest` run for right before committing (see PR / Commit below) — running it between every edit is slower than the feedback loop needs to be.

## Conventions

All Python code follows `.agents/rules/general.md` and the `python-conventions` skill. Key rules agents frequently violate:

- `from __future__ import annotations` at the top of every file.
- Explicit type annotations on all function signatures and module-level variables.
- `collections.abc` over `typing` for generic types (`Sequence`, `Iterator`, etc.).
- `from typing_extensions import override` and use `@override` on every method that overrides a base class or Protocol method. `@override` catches signature mismatches in subclasses at type-check time.
- No default parameter values on public API functions. Callers pass all arguments explicitly. Pydantic model fields are exempt. Dependency-injection seam parameters (e.g., `http_client`, `secret_prompt`) may have defaults when the public API callers always pass through.
- Keyword-only arguments for functions with 5+ parameters.
- All public API functions are `async` — one consistent mental model for consumers. `should_refresh()` is the one sync exception (pure datetime arithmetic). `CredentialStore.*` methods are sync (local I/O). The CLI wraps async calls in `asyncio.run()`. This is a deliberate design choice per spec §2.3, not a rule violation.
- No `print()` in library code. Use `logging` at `DEBUG` level.
- No bare `except:`. No `except Exception: pass`. Catch specific exceptions.
- Secrets are never passed through `str()` or `repr()`. Secret fields use `Field(repr=False)`. Use the redaction layer (`redact_body`, `redact_url`) for HTTP bodies and URLs.
- Use Pydantic for all data crossing process, network, config, or serialization boundaries.

## Ground Rules

- Be skeptical and do research. Verify before acting. Acknowledge uncertainty when you lack information.
- Do not commit secrets, API keys, or real user data.
- Do not add telemetry or hidden network calls. AuthLM has zero telemetry by design.
- Do not edit `uv.lock` by hand. Use `uv lock`.
- Do not add new runtime dependencies without explicit instruction. Provider SDKs go in `[project.optional-dependencies]`, never in core `dependencies`.
- Do not store credentials in plaintext. OS keychain is the default; plaintext file storage is opt-in and must warn.
- Do not add subscription/session-extraction methods without a `warning` field. The library informs; the integrator decides policy.
- Do not auto-refresh tokens on every `get_credential()` call. Refresh is explicit (`get_valid_credential()` or `refresh()`).
- Do not validate warned methods without `force=True`. Validation calls are detectable by providers.
- Keep changes scoped. For a bug fix, make the narrowest change that resolves the reported, reproduced behavior. Extend a fix to sibling providers/methods only after *confirming* (by reproducing) that they share the same defect — an "others might also be affected" hunch is not enough to widen the change. Do not refactor a shared abstraction (e.g. `_oauth_helpers.py`, `registry.py`) to fix one caller unless the narrow fix is unavailable or the refactor is itself the confirmed fix.
- **Never commit or push gitignored files.** `.agents/audits/`, `.agents/plans/`, `.worktrees/`, and `opencode.json` are gitignored. Do not `git add -f` them. Use `git check-ignore <path>` if unsure.

## Testing

- Unit tests: `tests/unit/` — use `respx` for HTTP mocking, `MemoryStore` for credential storage.
- Integration tests: `tests/integration/` — v0.2.0 (will use `pytest-recording` VCR.py cassettes).
- Cassettes live in `tests/cassettes/` (v0.2.0) and must have all secrets scrubbed (`Authorization` headers, `access_token`, `refresh_token`, `code`, `client_secret`).
- Never commit live tokens. CI fails on patterns: `sk-`, `xoxb-`, `ghp_`, `ya29.`, `Bearer [A-Za-z0-9_-]{20,}`.
- Tests must not touch the real OS keychain. `conftest.py` sets `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` and redirects `AUTHLM_USER_PATH` to `tmpdir`.
- Add tests for any behavior you change.

## Changelog

`CHANGELOG.md` follows [Keep a Changelog 2.0.0](https://keepachangelog.com/en/1.1.0/) (per spec §11.3) and Semantic Versioning. Maintain it as part of the change itself, not as an afterthought:

- **Every user-facing change gets an entry** under `## [Unreleased]` at the top of the file, added in the same commit/PR as the change — not batched later. User-facing means: anything a consumer of the public API, CLI, or exception hierarchy would notice — new/changed/removed functions, CLI flags, error types, credential fields, default behavior. Pure internal refactors, test-only changes, and CI/tooling tweaks do not need an entry.
- **Use the standard categories** under `[Unreleased]`, only including the ones that apply: `### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed`, `### Security`. Don't invent other headers.
- **One bullet per change**, imperative present tense (matches commit style), referencing the affected symbol in backticks, e.g.:
  ```markdown
  ### Fixed
  - `refresh()` now preserves the existing refresh token when the token endpoint omits one on rotation
  ```
- **Security-relevant changes** (anything touching `stores/`, `connection_methods/`, `_auth_table.py`, or redaction) always get a `### Security` entry, even if also listed under `Fixed`/`Changed`, and should prompt a check of whether `SECURITY.md` also needs updating.
- **Don't hand-write version headers or dates.** `## [Unreleased]` stays until a release; the release process (spec §11.3) turns it into `## [X.Y.Z] - YYYY-MM-DD` and opens a fresh empty `## [Unreleased]`. Agents should not pre-emptively create version-numbered sections.
- **Before treating a task as done**, check `git diff CHANGELOG.md` (or equivalent) to confirm an entry was actually added when the change was user-facing — this is easy to forget and easy to verify.

## PR / Commit

- Run `ruff check . && ruff format . && mypy src/authlm && pytest` before committing.
- Follow the `commit-conventions` skill. Key rules:
  - **Conventional Commits format:** `<type>[scope]: <description>` — allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - **Imperative, present tense:** `add`, `fix`, `remove` — not `added`, `fixed`, `removes`.
  - **Under 72 characters**, no trailing period, no emojis.
  - **Atomic commits:** one self-contained logical change per commit. Do not mix unrelated concerns.
  - **Signed commits:** use `git commit -S` (GPG/SSH signing) so commits show as "Verified" on GitHub. Do NOT use `--signoff` — no `Signed-off-by:` trailers in commit messages.
  - **Body:** add when context is needed; wrap at ~72 chars. Use a heredoc for multiline messages.
  - **Footers:** `Fixes #123`, `Refs: #456`, `BREAKING CHANGE:` footer for major changes.
  - **No `Co-authored-by:` trailers.** Never add `Co-authored-by:` to commit messages.
- Squash-merge to `main`. Trunk-based: `main` + short-lived feature branches.
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`.
- On first push of a new branch: `git push -u origin <branch>`.
- Do not bypass signing with `--no-gpg-sign` or skip hooks with `--no-verify` unless explicitly requested.

## Security-Sensitive Areas

- `src/authlm/stores/` — credential storage. Changes require maintainer review and a `SECURITY.md` update.
- `src/authlm/connection_methods/` — OAuth flows and token handling. Changes to PKCE redirect handling, token exchange, or error classification require careful review (the loopback server, PKCE pair generation, and redaction layer are all in this surface).
- `src/authlm/_auth_table.py` — OAuth client IDs, endpoints, scopes. Adding a new provider or changing an existing endpoint must be done as a single atomic change with the matching test update.
- `src/authlm/api.py` — public async API. The `refresh()` path handles refresh-token rotation; any change to it must preserve the "keep the old refresh token if the server omits one" fallback.
- `src/authlm/validation.py` — validation probes and warned-method policy. `validate()` raises `PermissionError` for warned-method refusals — this is a deliberate choice over `AuthLMError`; do not change without updating the spec. It also raises `AuthLMError` for `chatgpt_oauth_*` methods because they lack validation endpoint entitlement.
- `src/authlm/cli/` — the CLI surface (5 commands). Changes to CLI semantics (e.g., how warnings are surfaced, how `eval $(authlm env ...)` is routed) require careful review. The CLI uses `click.prompt(..., hide_input=True)` for secret input and routes device-code prompts to stderr; do not change these without confirming `tests/unit/test_cli_connect.py` and `tests/unit/test_cli_env.py` still pass.
- `src/authlm/credentials.py` — secret fields must use `Field(repr=False)`. Never add a secret field without this.
- VCR cassettes — must be scrubbed of all secrets.
- `SECURITY.md` — threat model and disclosure process.

## Further Context

- `.agents/specs/v0.1.0-authlm.md` — full v0.1.0 design spec. Read before architectural work.
- `.agents/specs/v0.2.0-authlm.md` — v0.2.0 outline (plugin system, models.dev, long-tail providers).
- `.agents/specs/v0.3.0-authlm.md` — v0.3.0 outline (file-locking, Vault/Bitwarden/1Password, audit log).
- `.agents/specs/v1.0.0-authlm.md` — v1.0.0 outline (API freeze, stable release).
- `.agents/rules/general.md` — project-wide coding rules (DRY, KISS, YAGNI, error handling, etc.).
- `CONTRIBUTING.md` — contributor guide.
- `SECURITY.md` — threat model, reporting a vulnerability, supported backends.
