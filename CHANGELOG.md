# Changelog

All notable changes to AuthLM are documented in this file.

The format is based on [Keep a Changelog 2.0.0](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding: `pyproject.toml` with hatchling build, ruff, mypy (strict),
  and pytest configuration.
- `authlm` package skeleton with `py.typed` marker and dynamic version sourced from
  `internal/authlm/_version.py`.
- Core exception hierarchy in `authlm.errors` (`AuthLMError` and seven subclasses).
- Core credential types in `authlm.credentials` (Pydantic models: `ApiKeyCredential`,
  `OAuthCredential`, `AwsCredential`, `AzureAdCredential`) with a discriminated
  `CredentialUnion`.
- Test infrastructure: `tests/conftest.py` with environment isolation fixtures and a
  smoke test.
