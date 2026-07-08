<!-- prettier-ignore -->
<div align="center">

# AuthLM

*One auth layer for any AI provider — OpenAI, Anthropic, Google, and more — with OS-keychain storage and OAuth built in.*

[![CI](https://github.com/vihaan-g/authlm/actions/workflows/ci.yml/badge.svg)](https://github.com/vihaan-g/authlm/actions/workflows/ci.yml)
[![CodeQL](https://github.com/vihaan-g/authlm/actions/workflows/codeql.yml/badge.svg)](https://github.com/vihaan-g/authlm/actions/workflows/codeql.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/authlm)](https://pypi.org/project/authlm/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](https://github.com/vihaan-g/authlm/releases)

:star: If you like this project, star it on GitHub!

[Quick start](#quick-start) • [CLI](#cli) • [API](#api) • [Stores](#credential-stores) • [Roadmap](#roadmap)

</div>

AuthLM is a Python library that handles authentication and credential management for AI provider APIs — so your app doesn't have to hand-roll OAuth flows, token refresh, or plaintext key storage for every provider you support. It is **auth-only** by design: AuthLM doesn't route requests, pick models, or replace an inference library. It does one job, hands you a working credential, and gets out of the way.

## Quick start

```bash
pip install authlm
```

```python
import authlm
from datetime import timedelta
from openai import AsyncOpenAI

# Connect once — interactive API key prompt, stored in OS keychain
await authlm.connect("openai", alias="default", method_id="api_key")

# Get a valid credential — auto-refreshes if expired or expiring soon
cred = await authlm.get_valid_credential("openai", alias="default", margin=timedelta(minutes=5))

# Use with any inference library
client = AsyncOpenAI(api_key=cred.secret)
```

Multiple accounts, one provider:

```python
await authlm.connect("openai", alias="personal", method_id="api_key")
await authlm.connect("openai", alias="work", method_id="api_key")

work_cred = await authlm.get_valid_credential("openai", alias="work", margin=timedelta(minutes=5))
```

Check if your credential still works:

```python
await authlm.validate(cred, force=True)  # probes the provider's API
```

## Why AuthLM?

Every AI provider speaks its own dialect of auth: some want a simple API key, some support OAuth with browser-based PKCE flows, some use headless device-code flows, and some rotate refresh tokens in ways that are easy to get wrong. Most libraries treat credentials as an afterthought — reading from env vars or plaintext files.

AuthLM abstracts all of that into one consistent API. Adding a new provider to your app is a matter of picking a provider ID, not building a new auth integration from scratch.

| | AuthLM | `llm keys` | LiteLLM | Provider SDKs |
|---|---|---|---|---|
| OS keychain storage | Yes | No (plaintext JSON) | No | No |
| OAuth (PKCE + device code) | Yes | No | No | No |
| Token refresh + rotation | Yes | No | No | No |
| Multi-account (alias) | Yes | Partial | No | No |
| Multi-provider | Yes (4 first-party) | Partial | Yes | No (one each) |
| Plugin system | v0.2.0 | No | No | No |
| Validation probes | Yes | No | No | No |
| Inference | No | Yes | Yes | Yes |
| Telemetry | None | — | — | — |

## Features

- **OS keychain by default** — macOS Keychain, Windows Credential Manager, Linux Secret Service via `keyring`. Never plaintext.
- **Multiple connection methods** — API key, OAuth browser (PKCE), OAuth device code. Warning-gated methods require explicit confirmation.
- **Token refresh with rotation** — persists new access and refresh tokens atomically, preventing the common "kept the old refresh token" failure mode.
- **Multi-account** — every credential is keyed by `(provider, alias)`. `personal` and `work` OpenAI accounts coexist.
- **Fingerprint-based change detection** — `compute_fingerprint()` stores a truncated SHA-256 of the secret; `authlm status` warns if the secret has changed since last connect.
- **Validation probes** — `validate()` issues a lightweight API call to confirm a credential works. Warned methods require `force=True`.
- **Public OAuth client IDs** — bundled client IDs for OpenAI Codex, Anthropic Claude Code, and Google AI Studio. Override via env vars.
- **5-command CLI** — `connect`, `list`, `status`, `disconnect`, `env` with shell/docker/GitHub Actions export formats.
- **Zero telemetry** — no analytics, no phone-home, no crash reports.

## What it is not

- **Not an inference library.** Use LiteLLM, the OpenAI SDK, the Anthropic SDK, or `llm` for model calls.
- **Not a model router.** Use LiteLLM.
- **Not a SaaS integration platform.** Use Nango or Composio for SaaS OAuth.
- **Not a secret broker for running agents.** Use Infisical Agent Vault for agent-runtime secret injection.

## Installation

```bash
pip install authlm                       # base + 4 providers
pip install "authlm[openai]"             # installs openai SDK extra
pip install "authlm[all]"                # all provider SDK extras
```

From source:

```bash
git clone https://github.com/vihaan-g/authlm.git
cd authlm
uv sync --all-extras
```

## API

AuthLM exposes six public async functions and a handful of types. Everything is `async` for API consistency.

| Function | Description |
|---|---|
| `connect(provider, alias, method_id)` | Run an interactive auth flow and persist the credential. |
| `get_credential(provider, alias)` | Fast store read — returns the credential as-is, even if expired. No network. |
| `get_valid_credential(provider, alias, margin)` | Returns a usable credential — auto-refreshes if expired or within margin. |
| `refresh(provider, alias)` | Force-refreshes an OAuth credential via the token endpoint. |
| `should_refresh(credential, margin)` | Pure datetime check — returns `True` if expired or within margin. |
| `validate(credential, *, force)` | Probes the credential against the provider's validation URL. |

### Credential types

| Type | Fields |
|---|---|
| `ApiKeyCredential` | `provider`, `alias`, `method_id`, `secret` |
| `OAuthCredential` | `provider`, `alias`, `method_id`, `access_token`, `refresh_token`, `expires_at`, `scopes` |

Use `CredentialUnion` for discriminated unions, and `parse_credential()` to deserialize from JSON.

### Supported providers

| Provider ID | API Key | OAuth PKCE | OAuth Device Code |
|---|---|---|---|
| `openai` | Yes | Yes | Yes |
| `anthropic` | Yes | Yes | Yes |
| `google` | Yes | Yes | — |
| `openrouter` | Yes | — | — |

### Error hierarchy

All exceptions inherit from `AuthLMError`. Key types:

| Exception | When |
|---|---|
| `CredentialNotFound` | No credential stored for `(provider, alias)` |
| `RefreshFailed` | Transient network error from token endpoint |
| `ReconnectionRequired` | Refresh token is dead — re-run `connect()` |
| `AccessDenied` | 403 from provider (token lacks entitlement) |
| `TokenEndpointError` | Other token endpoint error |
| `SecretStoreError` | Credential store persistence failure |

## CLI

```bash
# Connect a provider
authlm connect openai --alias work

# List all stored credentials
authlm list

# Inspect credentials, optionally probe them
authlm status openai --all --validate

# Delete a credential
authlm disconnect openai --alias work

# Export to shell, Docker, or GitHub Actions
eval "$(authlm env openai --alias work)"
authlm env openai --export-format github
```

| Command | Purpose |
|---|---|
| `connect <provider>` | Interactive auth flow. `--alias`, `--method`, `--include-warned`, `--store` |
| `list` | ASCII table of stored credentials. `--store`, `--metadata-path` |
| `status [provider]` | Per-credential metadata. `--all`, `--validate`, `--force`, `--backend` |
| `disconnect <provider>` | Delete credential + metadata. `--yes` to skip confirmation |
| `env <provider>` | Export as env vars. `--export-format shell\|docker\|github` |

> [!TIP]
> Non-TTY environments must pass `--method` — `connect` won't open an interactive picker in CI.

## Credential stores

| Backend | Description | Writable |
|---|---|---|
| `KeyringStore` (default) | OS keychain — macOS Keychain, Windows Credential Manager, Linux Secret Service. | Yes |
| `EncryptedFileStore` | Fernet-encrypted (AES-128-CBC + HMAC-SHA256) file on disk. PBKDF2-derived key, 600k iterations. | Yes |
| `EnvStore` | Read-only from env vars (`OPENAI_API_KEY`, etc.). Only `alias="default"`. | No |
| `MemoryStore` | In-process dict. Tests only. Cleared on exit. | Yes |

Override: `AUTHLM_STORE=encrypted_file authlm connect openai` or `authlm.set_store(store)`.

## Environment variables

| Variable | Purpose |
|---|---|
| `AUTHLM_STORE` | Override the default store backend (`keyring`, `encrypted_file`, `env`, `memory`). |
| `AUTHLM_USER_PATH` | Override the authlm user data directory. |
| `AUTHLM_METADATA_PATH` | Override the path to `metadata.json`. |
| `AUTHLM_PASSPHRASE` | Passphrase for `EncryptedFileStore`. Prefer the interactive prompt when available. |
| `AUTHLM_PKCE_PORT_OVERRIDE` | Override the loopback port for PKCE OAuth browser flows. |
| `AUTHLM_OPENAI_CLIENT_ID` | Override the default OpenAI OAuth client ID. |
| `AUTHLM_ANTHROPIC_CLIENT_ID` | Override the default Anthropic OAuth client ID. |
| `AUTHLM_GOOGLE_CLIENT_ID` | Override the default Google OAuth client ID. |

## Roadmap

| Version | Theme | Key deliverables |
|---|---|---|
| **v0.1.0** | Foundation | 4 providers, 3 connection methods, 4 stores, 5-command CLI. Available now. |
| **v0.2.0** | Extensibility | Plugin system (pluggy), models.dev integration, long-tail providers, `authlm import/export llm`, Homebrew tap. |
| **v0.3.0** | Robustness | File-locking, Vault/Bitwarden/1Password backends, audit log, client_credentials grant. |
| **v1.0.0** | Stable release | API-locked SemVer, stability guarantee, comprehensive integration tests. |

## Development

```bash
uv sync --all-extras                # install all deps
uv run pytest                       # unit tests, sub-second
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/authlm              # typecheck (strict)
uv run authlm --help                # CLI smoke test
```

CI runs the full matrix: 3 OS × 4 Python versions, plus `pip-audit`, `secrets-grep`, ruff, and mypy strict.

## Security

AuthLM is a credential library — security is the product. See [SECURITY.md](SECURITY.md) for the threat model, per-backend security notes, redaction policy, and disclosure process.

Report vulnerabilities privately via GitHub's "Report a vulnerability" button on the Security tab — not via public issues.
