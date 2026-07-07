# Contributing to AuthLM

Thank you for taking the time to contribute.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Please report
unacceptable behavior via GitHub's private reporting.

## Security vulnerabilities

**Do not file public issues for security vulnerabilities.** See
[SECURITY.md](SECURITY.md) for the coordinated disclosure process and the
project's threat model.

## Getting started

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/vihaan-g/authlm.git
cd AuthLM
uv sync --all-extras
source .venv/bin/activate
```

### Run everything locally

```bash
uv run pytest                       # unit tests
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy src/authlm              # typecheck (strict)
uv run authlm --help                # CLI smoke test
```

CI runs the full matrix on every push: three OSes (Ubuntu, macOS, Windows)
across four Python versions (3.11, 3.12, 3.13, 3.14), plus pip-audit,
secrets-grep, ruff, and mypy strict.

## Submitting changes

1. Create a short-lived feature branch off `main`.
2. Make your changes, and add or update tests in `tests/unit/`.
3. Run the full pre-commit check before pushing:

   ```bash
   uv run ruff check . && uv run ruff format . && uv run mypy src/authlm && uv run pytest
   ```

4. Commit with a [Conventional Commits][conventional-commits] message (imperative,
   present tense, under 72 characters). Sign commits with `git commit -S` — no
   `--signoff`.

5. Push and open a pull request against `main`. Every PR must pass all CI jobs
   before merge. Merges are squash-merged.

[conventional-commits]: https://www.conventionalcommits.org

### Changelog

Every user-facing PR must add a line under `## [Unreleased]` in
`CHANGELOG.md`, categorized as `### Added`, `### Fixed`, or `### Changed`.

### Writing tests

Tests use `respx` for HTTP mocking and `MemoryStore` for credential storage.
Never use real API keys. Conftest fixtures (`stub_store`, `runner`) are shared
across test modules.

### Adding a new provider

v0.1.0 uses in-tree providers. A plugin system is planned for v0.2.0.

1. Add the provider's OAuth configuration to `src/authlm/_auth_table.py`.
2. Create `src/authlm/providers/<provider_id>.py` implementing the `Provider`
   Protocol (see `providers/base.py`).
3. Register the provider in `providers/registry.py:_build_providers()`.
4. Add tests in `tests/unit/test_providers_<provider_id>.py`.
5. If the provider needs an SDK, add it to `[project.optional-dependencies]` in
   `pyproject.toml`.
6. Add the env var mapping to `src/authlm/stores/env_store.py:_ENV_VAR_MAP`.

## Community

See [AGENTS.md](AGENTS.md) for agent-facing conventions and
[SECURITY.md](SECURITY.md) for the threat model and security policy.

## Release process

1. All CI jobs pass on `main`.
2. Update `CHANGELOG.md` — replace `[Unreleased]` with a version heading and
   date, then clear the unreleased section.
3. Run `uv run python -m build` to verify the wheel.
4. Tag the release: `git tag -s vX.Y.Z -m "vX.Y.Z"`.
5. Push: `git push origin main --follow-tags`.
6. CI publishes to PyPI via Trusted Publishing.
