# Contributing to AuthLM

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/vihaan-g/AuthLM.git
cd AuthLM
uv sync --extra test --all-extras
source .venv/bin/activate
```

Run the test suite:

```bash
uv run pytest                       # 240+ unit tests
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/authlm              # typecheck (strict)
uv run authlm --help                # CLI smoke test
```

## How to add a provider

v0.1.0 supports in-tree providers only. v0.2.0 will add a plugin system.

To add a provider in v0.1.0:

1. Add the provider's OAuth configuration to `src/authlm/_auth_table.py` if it supports OAuth.
2. Create `src/authlm/providers/<provider_id>.py` implementing the `Provider` Protocol (see `providers/base.py`).
3. Register the provider in `providers/registry.py:_build_providers()`.
4. Add tests in `tests/unit/test_providers_<provider_id>.py`.
5. If the provider needs an SDK, add it to `[project.optional-dependencies]` in `pyproject.toml`.
6. Add the env var mapping to `src/authlm/stores/env_store.py:_ENV_VAR_MAP`.

## Testing rule

Any PR that touches a provider or connection method must add or update tests. Tests use `respx` for HTTP mocking and `MemoryStore` for credential storage. Never use real API keys in tests.

## Security rule

PRs that change credential storage (`stores/`), connection methods (`connection_methods/`), or the auth table (`_auth_table.py`) require maintainer review. If your PR changes how credentials are stored, transmitted, or redacted, update `SECURITY.md`.

## Changelog rule

Every user-facing PR must add a line under `## [Unreleased]` in `CHANGELOG.md`. Follow the existing format (categorize under `### Added`, `### Fixed`, or `### Changed`).

## Release process

1. All CI jobs must pass: lint, test (3 OS × 4 Python), CLI smoke, security (pip-audit).
2. Confirm `## [Unreleased]` in `CHANGELOG.md` is the correct content for the release.
3. Add `## [X.Y.Z] - YYYY-MM-DD` above `[Unreleased]`, leave `[Unreleased]` empty.
4. `git tag -s vX.Y.Z -m "vX.Y.Z"`
5. `git push origin main --follow-tags`
6. CI's release workflow builds, attaches to GitHub Release, and publishes to PyPI via Trusted Publishing.

## Commit conventions

Conventional Commits: `<type>[scope]: <description>`. Imperative present tense, under 72 chars. Signed commits (`git commit -S`). No `--signoff`.

See [AGENTS.md](AGENTS.md) for agent-facing coding conventions and [SECURITY.md](SECURITY.md) for the threat model.
