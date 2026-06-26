# AuthLM

[![CI](https://github.com/vihaan-g/AuthLM/actions/workflows/ci.yml/badge.svg)](https://github.com/vihaan-g/AuthLM/actions/workflows/ci.yml)
[![CodeQL](https://github.com/vihaan-g/AuthLM/actions/workflows/codeql.yml/badge.svg)](https://github.com/vihaan-g/AuthLM/actions/workflows/codeql.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--release-orange)](https://github.com/vihaan-g/AuthLM/releases)

**OS-keychain-backed authentication for AI providers. API keys, OAuth, token refresh, and multi-account support — auth only, composes with any inference library.**

AuthLM is a Python library that manages authentication and credentials for AI provider APIs (OpenAI, Anthropic, Google, Ollama, OpenRouter, and others). It is **auth-only** — it does not generate text, route requests, or choose models. It handles the hard part: secure storage, OAuth flows, token refresh, and multi-provider credential management. You hand the resulting credential to whatever inference library you already use.

## Status

**Pre-release. v0.1.0 in development. Not yet on PyPI.**

**Implemented today** (milestone 1, all tests passing on macOS/Linux/Windows × Python 3.11/3.12/3.13):

- Pydantic `Credential` types (`ApiKeyCredential`, `OAuthCredential`) with discriminated union
- Exception hierarchy (`AuthLMError` + 7 specific subclasses)
- 4 `CredentialStore` backends: `KeyringStore`, `EncryptedFileStore`, `EnvStore`, `MemoryStore`
- Store auto-selection via `get_default_store` (keychain → encrypted file → env, with warning)
- `Provider` and `ConnectionMethod` Protocols + `OAuthGrant` enum
- pluggy plugin system (hookspecs, loader, entry-point isolation)
- `MetadataStore` for non-secret credential metadata (fingerprints, timestamps, scopes)
- NTFS ACL enforcement on Windows (owner-only file permissions, not just POSIX `chmod 0o600`)

**Planned for v0.1.0** (not yet implemented):

- Public async API (`api.py`): `get_credential`, `get_valid_credential`, `refresh`, `validate`, `connect`
- 5-command CLI (`cli.py`): `connect`, `list`, `status`, `disconnect`, `env`
- Connection methods: API key, OAuth PKCE (browser), OAuth device code
- 5 concrete providers: OpenAI, Anthropic, Google, Ollama, OpenRouter
- models.dev integration with vendored snapshot fallback
- Validation probes (lightweight API calls to verify a credential works)

See the [design spec](.agents/specs/v0.1.0-authlm.md) for the full v0.1.0 architecture.

## Why AuthLM?

Most AI libraries treat credentials as an afterthought:

- **`llm`** stores API keys as plaintext JSON in `~/.config/io.datasette.llm/keys.json`.
- **LiteLLM** and the **official provider SDKs** read from env vars or expect you to pass keys inline. No keychain, no OAuth, no refresh.
- **No widely-used library** handles OAuth PKCE, device-code flows, refresh-token rotation, or multi-account keying for AI providers.

AuthLM is the dedicated auth layer. OS keychain by default, OAuth flows, token refresh with rotation, multi-provider, multi-account. It composes with any inference library — use LiteLLM, the OpenAI SDK, or Anthropic SDK for the actual calls; AuthLM just hands you a valid credential.

## Features

- **OS keychain by default** — macOS Keychain, Windows Credential Manager, Linux Secret Service via `keyring`. Never plaintext.
- **Multiple connection methods** — API key, OAuth browser (PKCE), OAuth device code. Warning-gated methods (e.g., Anthropic Claude Pro OAuth) require explicit user confirmation.
- **Token refresh with rotation** — centralized implementation persists both new access and refresh tokens atomically, preventing the common "kept the old refresh token" failure mode.
- **Multi-account** — every credential is keyed by `(provider, alias)`. `personal` and `work` OpenAI accounts coexist.
- **Plugin system** — pluggy-based (same engine as `pytest`). Third-party providers and stores register via entry points.
- **5-command CLI** — `connect`, `list`, `status`, `disconnect`, `env`. Thin sync wrapper over the async library.
- **Zero telemetry** — no analytics, no phone-home, no crash reports. By design.

## What it is not

- **Not an inference library.** Use LiteLLM, the OpenAI SDK, the Anthropic SDK, or `llm` for the actual model calls.
- **Not a model router.** Use LiteLLM.
- **Not a SaaS integration platform.** Use Nango or Composio for SaaS OAuth.
- **Not a secret broker for running agents.** Use Infisical Agent Vault for agent-runtime secret injection.

## Comparison

Target feature set for v0.1.0 (in development):

| | AuthLM | `llm keys` | LiteLLM | Provider SDKs |
|---|---|---|---|---|
| OS keychain storage | Yes | No (plaintext JSON) | No | No |
| OAuth (PKCE + device code) | Planned | No | No | No |
| Token refresh + rotation | Planned | No | No | No |
| Multi-account (alias) | Planned | Partial | No | No |
| Multi-provider | Yes (5 + plugins) | Partial | Yes | No (one each) |
| Plugin system | Yes (pluggy) | No | No | No |
| Inference | No | Yes | Yes | Yes |
| Telemetry | None | — | — | — |

## Installation

**Not yet on PyPI.** Install from source for development or experimentation:

```bash
git clone https://github.com/vihaan-g/AuthLM.git
cd AuthLM
uv sync --all-extras
```

Once v0.1.0 ships, the install will be:

```bash
pip install authlm                       # base + 5 providers
pip install "authlm[openai]"             # installs openai SDK extra
pip install "authlm[all]"                # all provider SDK extras
```

## Quick start

> **Note:** The public API below is the target for v0.1.0. It is not yet implemented — `api.py` and `cli.py` are the next milestone. See [Status](#status) for what works today.

```python
import authlm
from openai import AsyncOpenAI

# Connect once — interactive prompt for API key, stored in OS keychain
await authlm.connect("openai", alias="default")

# Get a valid credential — auto-refreshes if expired or within refresh margin
cred = await authlm.get_valid_credential("openai", alias="default")

# Use with any inference library
client = AsyncOpenAI(api_key=cred.secret)
```

Multiple accounts:

```python
await authlm.connect("openai", alias="personal")
await authlm.connect("openai", alias="work")

work_cred = await authlm.get_valid_credential("openai", alias="work")
```

## CLI

```bash
authlm connect openai --alias personal           # interactive: pick method, enter key / OAuth
authlm list                                       # Provider | Alias | Method | Backend | Last Validated
authlm status openai --all                        # metadata for all aliases; --validate to probe
authlm disconnect openai --alias personal         # delete credential + metadata
authlm env openai --alias work                    # export as shell env vars: eval "$(authlm env openai --alias work)"
```

## Credential stores

| Backend | Use case |
|---|---|
| `KeyringStore` (default) | OS keychain — macOS Keychain, Windows Credential Manager, Linux Secret Service. |
| `EncryptedFileStore` | Headless/CI when no keychain is available. Fernet (AES-128-CBC + HMAC-SHA256) with PBKDF2-derived key. POSIX `chmod 0o600` / Windows NTFS ACLs enforced. |
| `EnvStore` | Read-only from env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...). CI, Docker, ephemeral. Never writes. |
| `MemoryStore` | In-process. Tests only. Cleared on exit. |

Override the default with `AUTHLM_STORE=encrypted_file authlm connect openai`.

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras                # install all deps including test extras
uv run pytest                       # 93 unit tests, sub-second
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/authlm              # typecheck (strict)
```

CI runs the full matrix on every push: 3 OS (Ubuntu, macOS, Windows) × 3 Python (3.11, 3.12, 3.13), plus `pip-audit`, `secrets-grep`, ruff, and mypy strict.

See [AGENTS.md](AGENTS.md) for the full contribution guide, coding conventions, and commit rules.

## Security

AuthLM is a credential library — security is the product. See [SECURITY.md](SECURITY.md) for:

- The full threat model (what AuthLM does and does not protect against)
- Per-backend security notes
- Redaction policy (what gets scrubbed in logs, exceptions, and VCR cassettes)
- Coordinated disclosure policy (72h acknowledgement, 14-day patch SLA for critical issues)

**Report vulnerabilities privately** via GitHub's "Report a vulnerability" button on the Security tab — not via public issues.

## Contributing

Trunk-based: `main` + short-lived feature branches, squash-merge. Conventional Commits with signed commits (`git commit -S`, no `--signoff`). See [AGENTS.md](AGENTS.md) for the full guide.

## License

Apache-2.0. See [LICENSE](LICENSE).
