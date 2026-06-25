# AuthLM

**Authentication and credential management for AI provider libraries.**

AuthLM is a Python library that manages authentication and credentials for AI provider APIs (OpenAI, Anthropic, Google, and others). It is **auth-only** — it does not generate text, route requests, or choose models. It handles the hard part: secure storage, OAuth flows, token refresh, and multi-provider credential management.

**Status:** v0.1.0 — not yet released. See [`.agents/specs/v0.1.0-authlm.md`](.agents/specs/v0.1.0-authlm.md) for the design spec.

## What it will do

- Store credentials in the OS keychain by default (macOS Keychain, Windows Credential Manager, Linux Secret Service). Never plaintext.
- Support multiple connection methods per provider: API key, OAuth browser (PKCE), OAuth device code.
- Auto-refresh expired OAuth tokens with explicit `get_valid_credential()` API.
- Support multiple accounts per provider via `(provider, alias)` keying.
- Provide a 5-command CLI: `connect`, `list`, `status`, `disconnect`, `env`.
- Use a pluggy-based plugin system for adding providers (5 built-in: OpenAI, Anthropic, Google, Ollama, OpenRouter).
- Have zero telemetry.

## What it is not

- Not an inference library. Use LiteLLM, OpenAI SDK, Anthropic SDK, or `llm`.
- Not a model router. Use LiteLLM.
- Not a SaaS integration platform. Use Nango or Composio.
- Not a secret broker for running agents. Use Infisical Agent Vault.

## Quick start (planned)

```python
import authlm
from openai import AsyncOpenAI

await authlm.connect("openai", alias="default")
cred = await authlm.get_valid_credential("openai", alias="default")
client = AsyncOpenAI(api_key=cred.secret)
```

## Development

```bash
uv sync --extra test --all-extras
uv run pytest
uv run ruff check . && uv run ruff format . && uv run mypy src/authlm
```

See [AGENTS.md](AGENTS.md) for the full contribution guide.

## License

Apache-2.0. See [LICENSE](LICENSE).
