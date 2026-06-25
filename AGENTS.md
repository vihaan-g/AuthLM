# AGENTS.md

AuthLM is a Python library for managing authentication and credentials for AI providers (OpenAI, Anthropic, Google, etc.). Auth-only — it does not do inference. Apache-2.0. Full design: `.agents/specs/v0.1.0-authlm.md`.

## Project Structure

- `internal/authlm/` — the library source (note: `internal/`, not `src/`)
  - `api.py` — public async API (`get_credential`, `get_valid_credential`, `refresh`, `validate`, `connect`)
  - `credentials.py` — Pydantic Credential types (`ApiKeyCredential`, `OAuthCredential`, `AwsCredential`, `AzureAdCredential`)
  - `providers/` — built-in providers (v0.1.0: `openai`, `anthropic`, `google`, `ollama`, `openrouter`)
  - `connection_methods/` — `api_key.py`, `oauth_pkce.py`, `oauth_device.py`, `_oauth_helpers.py`
  - `stores/` — `keyring_store.py`, `encrypted_file_store.py`, `env_store.py`, `memory_store.py`
  - `hookspecs.py`, `plugins.py` — pluggy plugin system
  - `cli.py` — Click CLI (5 commands: connect, list, status, disconnect, env)
  - `errors.py` — exception hierarchy (`AuthLMError` base)
- `tests/` — `unit/`, `integration/`, `security/`, `cassettes/` (VCR.py)
- `.agents/specs/` — design specs (read before architectural work)
- `.agents/rules/general.md` — project-wide coding rules (read before any coding)

## Setup

- Requires Python 3.11+.
- Install uv first: `pip install uv` (or use `brew install uv`).
- Sync deps: `uv sync --extra test --all-extras`
- Activate: `source .venv/bin/activate` (or use `uv run <cmd>`)

## Commands

- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .` — run after changes
- **Typecheck:** `uv run mypy internal/authlm` — must pass with `--strict`
- **Test (focused):** `uv run pytest tests/unit/<area>` — run for the area you changed
- **Test (full):** `uv run pytest` — ask before running the full suite
- **Build:** `uv run python -m build`

## Conventions

All Python code follows `.agents/rules/general.md` and the `python-conventions` skill. Key rules agents frequently violate:

- `from __future__ import annotations` at the top of every file.
- Explicit type annotations on all function signatures and module-level variables.
- `collections.abc` over `typing` for generic types (`Sequence`, `Iterator`, etc.).
- `from typing_extensions import override` and use `@override` on every method that overrides a base class or Protocol method. This is a plugin-heavy library; `@override` catches signature mismatches in third-party subclasses at type-check time.
- No default parameter values on functions. Callers pass all arguments explicitly. Pydantic model fields are exempt.
- Keyword-only arguments for functions with 5+ parameters.
- No `async` without real I/O. All public API functions are async; `CredentialStore.*` and `should_refresh()` are sync (local I/O / pure computation only).
- No `print()` in library code. Use `logging` at `DEBUG` level.
- No bare `except:`. No `except Exception: pass`. Catch specific exceptions.
- Secrets are never passed through `str()` or `repr()`. Use the redaction layer in `authlm.logging`.
- Plugin modules import their SDKs lazily (inside `register_*` or `connect()`), never at module top level.
- Use Pydantic for all data crossing process, network, config, or serialization boundaries.

## Ground Rules

- Do not commit secrets, API keys, or real user data.
- Do not add telemetry or hidden network calls. AuthLM has zero telemetry by design.
- Do not edit `uv.lock` by hand. Use `uv lock`.
- Do not add new runtime dependencies without explicit instruction. Provider SDKs go in `[project.optional-dependencies]`, never in core `dependencies`.
- Do not store credentials in plaintext. OS keychain is the default; plaintext file storage is opt-in and must warn.
- Do not add subscription/session-extraction methods without a `warning` field. The library informs; the integrator decides policy.
- Do not auto-refresh tokens on every `get_credential()` call. Refresh is explicit (`get_valid_credential()` or `refresh()`).
- Do not validate warned methods without `force=True`. Validation calls are detectable by providers.
- Keep changes scoped. Avoid unrelated refactors.

## Testing

- Unit tests: `tests/unit/` — use `respx` for HTTP mocking, `MemoryStore` for credential storage.
- Integration tests: `tests/integration/` — use `pytest-recording` (VCR.py) cassettes.
- Cassettes live in `tests/cassettes/` and must have all secrets scrubbed (`Authorization` headers, `access_token`, `refresh_token`, `code`, `client_secret`).
- Never commit live tokens. CI fails on patterns: `sk-`, `xoxb-`, `ghp_`, `ya29.`, `Bearer [A-Za-z0-9_-]{20,}`.
- Tests must not touch the real OS keychain. `conftest.py` sets `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` and redirects `AUTHLM_USER_PATH` to `tmpdir`.
- Add tests for any behavior you change.

## PR / Commit

- Run `ruff check . && ruff format . && mypy internal/authlm && pytest` before committing.
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for every user-facing change.
- Follow the `commit-conventions` skill. Key rules:
  - **Conventional Commits format:** `<type>[scope]: <description>` — allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - **Imperative, present tense:** `add`, `fix`, `remove` — not `added`, `fixed`, `removes`.
  - **Under 72 characters**, no trailing period, no emojis.
  - **Atomic commits:** one self-contained logical change per commit. Do not mix unrelated concerns.
  - **Signed commits:** use `git commit -S` (GPG/SSH signing) so commits show as "Verified" on GitHub. Do NOT use `--signoff` — no `Signed-off-by:` trailers in commit messages.
  - **Body:** add when context is needed; wrap at ~72 chars. Use a heredoc for multiline messages.
  - **Footers:** `Fixes #123`, `Refs: #456`, `Co-authored-by:`. Use `BREAKING CHANGE:` footer for major changes.
- Squash-merge to `main`. Trunk-based: `main` + short-lived feature branches.
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`.
- On first push of a new branch: `git push -u origin <branch>`.
- Do not bypass signing with `--no-gpg-sign` or skip hooks with `--no-verify` unless explicitly requested.

## Security-Sensitive Areas

- `internal/authlm/stores/` — credential storage. Changes require maintainer review and a `SECURITY.md` update.
- `internal/authlm/connection_methods/` — OAuth flows and token handling.
- `internal/authlm/_auth_table.py` — OAuth client IDs, endpoints, scopes.
- VCR cassettes — must be scrubbed of all secrets.
- `SECURITY.md` — threat model and disclosure process.

## Further Context

- `.agents/specs/v0.1.0-authlm.md` — full design spec. Read before architectural work.
- `.agents/rules/general.md` — project-wide coding rules (DRY, KISS, YAGNI, error handling, etc.).
- `CONTRIBUTING.md` — contributor guide (planned).
- `SECURITY.md` — threat model, reporting a vulnerability (planned).
