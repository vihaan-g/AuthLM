# AuthLM

[![CI](https://github.com/vihaan-g/AuthLM/actions/workflows/ci.yml/badge.svg)](https://github.com/vihaan-g/AuthLM/actions/workflows/ci.yml)
[![CodeQL](https://github.com/vihaan-g/AuthLM/actions/workflows/codeql.yml/badge.svg)](https://github.com/vihaan-g/AuthLM/actions/workflows/codeql.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--release-orange)](https://github.com/vihaan-g/AuthLM/releases)

**OS-keychain-backed authentication for AI providers. API keys, OAuth, token refresh, and multi-account support — auth only, composes with any inference library.**

AuthLM is a Python library that manages authentication and credentials for AI provider APIs (OpenAI, Anthropic, Google, OpenRouter, and others). It is **auth-only** — it does not generate text, route requests, or choose models. It handles the hard part: secure storage, OAuth flows, token refresh, and multi-provider credential management. You hand the resulting credential to whatever inference library you already use.

## Status

**Pre-release. v0.1.0 in development. Not yet on PyPI.**

v0.1.0 ships 4 first-party providers, 3 connection methods, 4 credential stores, and a 5-command CLI. The plugin system, models.dev integration, and long-tail providers are deferred to v0.2.0. See [Roadmap](#roadmap) below.

See the [design spec](.agents/specs/v0.1.0-authlm.md) for the full v0.1.0 architecture.

## Why AuthLM?

Most AI libraries treat credentials as an afterthought:

- **`llm`** stores API keys in plaintext JSON by default (newer versions offer a keyring option).
- **LiteLLM** and the **official provider SDKs** read from env vars or expect you to pass keys inline. No keychain, no OAuth, no refresh.
- **No widely-used library** handles OAuth PKCE, device-code flows, refresh-token rotation, or multi-account keying for AI providers.

AuthLM is the dedicated auth layer. OS keychain by default, OAuth flows, token refresh with rotation, multi-provider, multi-account. It composes with any inference library — use LiteLLM, the OpenAI SDK, or Anthropic SDK for the actual calls; AuthLM just hands you a valid credential.

## Features

- **OS keychain by default** — macOS Keychain, Windows Credential Manager, Linux Secret Service via `keyring`. Never plaintext.
- **Multiple connection methods** — API key, OAuth browser (PKCE), OAuth device code. Warning-gated methods (e.g., Anthropic Claude Pro OAuth) require explicit user confirmation.
- **Token refresh with rotation** — centralized implementation persists both new access and refresh tokens atomically, preventing the common "kept the old refresh token" failure mode.
- **Multi-account** — every credential is keyed by `(provider, alias)`. `personal` and `work` OpenAI accounts coexist.
- **Fingerprint-based change detection** — `compute_fingerprint()` stores a truncated SHA-256 of the secret in metadata; `authlm status` warns if the secret has changed since last connect (detects keyring tampering or external rotation).
- **Public OAuth client IDs** — OpenAI Codex, Anthropic Claude Code, Google AI Studio client IDs are bundled in `_auth_table.py` (the same client IDs the official CLI tools use), so OAuth flows work out-of-the-box. Override per-provider via `AUTHLM_{OPENAI,ANTHROPIC,GOOGLE}_CLIENT_ID` env vars.
- **Validation probes** — `await authlm.validate(cred, force=True)` issues a lightweight API call (`GET /v1/models`, etc.) to confirm a credential works. Warned methods (Anthropic Claude Pro) require `force=True` and the library tells you why.
- **5-command CLI** — `connect`, `list`, `status` (with `--backend` and `--validate`), `disconnect`, `env`. `eval "$(authlm env openai)"` for shell; `--export-format github` for workflow `env:` blocks; non-TTY `connect` refuses to hang in CI.
- **Zero telemetry** — no analytics, no phone-home, no crash reports. By design.

## What it is not

- **Not an inference library.** Use LiteLLM, the OpenAI SDK, the Anthropic SDK, or `llm` for the actual model calls.
- **Not a model router.** Use LiteLLM.
- **Not a SaaS integration platform.** Use Nango or Composio for SaaS OAuth.
- **Not a secret broker for running agents.** Use Infisical Agent Vault for agent-runtime secret injection.

## Comparison

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

## Installation

**Not yet on PyPI.** Install from source for development or experimentation:

```bash
git clone https://github.com/vihaan-g/AuthLM.git
cd AuthLM
uv sync --all-extras
```

Once v0.1.0 ships, the install will be:

```bash
pip install authlm                       # base + 4 providers
pip install "authlm[openai]"             # installs openai SDK extra
pip install "authlm[all]"                # all provider SDK extras
```

## Quick start

```python
import authlm
from openai import AsyncOpenAI

# Connect once — interactive prompt for API key, stored in OS keychain
await authlm.connect("openai", alias="default")

# Get a valid credential — auto-refreshes if expired or within refresh margin
cred = await authlm.get_valid_credential("openai", alias="default", margin=timedelta(minutes=5))

# Use with any inference library
client = AsyncOpenAI(api_key=cred.secret)
```

Multiple accounts:

```python
await authlm.connect("openai", alias="personal")
await authlm.connect("openai", alias="work")

work_cred = await authlm.get_valid_credential("openai", alias="work", margin=timedelta(minutes=5))
```

## CLI

```bash
authlm connect openai --alias personal           # interactive: pick method, enter key / OAuth
authlm list                                       # Provider | Alias | Method | Backend | Last Validated
authlm status openai --all                        # metadata for all aliases; --validate to probe; --backend to show store
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

Override the default with `AUTHLM_STORE=encrypted_file authlm connect openai` or programmatically via `authlm.set_store(...)`.

## Roadmap

| Version | Theme | Key deliverables |
|---|---|---|
| **v0.1.0** | Foundation | 4 first-party providers, 3 connection methods, 4 stores, 5-command CLI, fingerprint-based change detection. First-party only — no plugin system. |
| **v0.2.0** | Extensibility & Ecosystem | Plugin system (pluggy), models.dev integration, long-tail providers (Mistral, Groq, DeepSeek, Cohere, ...), Ollama (no-auth), `authlm import llm` / `authlm export`, interactive CLI menu, doc site, Homebrew tap. |
| **v0.3.0** | Robustness & More Stores | File-locking (multi-process refresh safety), Vault/Bitwarden/1Password store backends, audit log, maintained SDK adapters, `client_credentials` OAuth grant. |
| **v1.0.0** | Stable Release | API-locked SemVer, stability guarantee, comprehensive integration tests, documentation complete, deprecated v0.x APIs removed. |

See `.agents/specs/v0.2.0-authlm.md`, `v0.3.0-authlm.md`, and `v1.0.0-authlm.md` for detailed outlines.

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras                # install all deps including test extras
uv run pytest                       # 242 unit tests, sub-second
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/authlm              # typecheck (strict)
uv run authlm --help                # CLI smoke test
```

CI runs the full matrix on every push: 3 OS (Ubuntu, macOS, Windows) × 4 Python (3.11, 3.12, 3.13, 3.14), plus `pip-audit`, `secrets-grep`, ruff, and mypy strict.

See [AGENTS.md](AGENTS.md) for the full contribution guide, coding conventions, and commit rules. See [CONTRIBUTING.md](CONTRIBUTING.md) for the human-facing contributor guide.

## Security

AuthLM is a credential library — security is the product. See [SECURITY.md](SECURITY.md) for:

- The full threat model (what AuthLM does and does not protect against)
- Per-backend security notes
- Redaction policy (what gets scrubbed in logs, exceptions, and VCR cassettes)
- Coordinated disclosure policy (72h acknowledgement, 14-day patch SLA for critical issues)

**Report vulnerabilities privately** via GitHub's "Report a vulnerability" button on the Security tab — not via public issues.

## Contributing

Trunk-based: `main` + short-lived feature branches, squash-merge. Conventional Commits with signed commits (`git commit -S`, no `--signoff`). See [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## License

Apache-2.0. See [LICENSE](LICENSE).
