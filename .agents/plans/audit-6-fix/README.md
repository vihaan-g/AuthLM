# Audit-6-Fix: v0.1.0 Release Audit Remediation

**Audit Source:** `.agents/audits/v0.1.0-release-audit.md`
**Date:** 2026-07-07

## Plan Files

| File | Scope | Items | Est. Effort |
|---|---|---|---|
| [`v0.1.0-release-blockers.md`](./v0.1.0-release-blockers.md) | Must fix before `git tag v0.1.0` | 4 tasks (P0–P1) | ~45 min |
| [`v0.1.1-patch.md`](./v0.1.1-patch.md) | First patch after v0.1.0 | 11 tasks (P2–P3) | ~3 hr |
| [`nice-to-have.md`](./nice-to-have.md) | Any future release (backlog) | 10 tasks (N1–N10) | ~1.5 hr |

## Release Blocker Summary

| Priority | Task | File | What |
|---|---|---|---|
| P0 | Task 1 | `README.md` | Fix broken `connect()` code examples — add missing `method_id` |
| P0 | Task 2 | `AGENTS.md` | Fix phantom `get_store()`/`is_tty()` references |
| P1 | Task 3 | `oauth_device.py`, `oauth_pkce.py` | Add `timeout=30.0` to two OAuth POST calls |
| P1 | Task 4 | `providers/{openai,anthropic,google}.py` | Accept optional `http_client` param to fix AsyncClient leak |

## v0.1.1 Patch Summary

| Priority | Category | Tasks |
|---|---|---|
| P2 | Security | Task 1: Set 0o700 on EncryptedFileStore parent dir |
| P2 | Documentation | Tasks 2–4: Env var reference table, clone URL, redaction scope |
| P3 | Testing | Tasks 5–10: Concurrent refresh race, store.set failure, KeyringStore errors, validate(force=True), Google/OpenRouter depth |

## Nice-to-Have Summary

| ID | Scope | What |
|---|---|---|
| N1 | CLI | Extract store-resolution helper into `_context.py` |
| N2 | Typing | TypedDict for OAuth response JSON |
| N3 | API | `DEFAULT_REFRESH_MARGIN` constant |
| N4 | Models | Pydantic `Field(description=...)` |
| N5 | Perf | mtime cache on MetadataStore._read() |
| N6 | Robustness | assert → explicit AuthLMError |
| N7 | Versioning | `__version_tuple__` |
| N8 | Perf | Merge two model_copy calls |
| N9 | DX | `get_user_data_path()` in top-level __all__ |
| N10 | Style | Google-style docstring for validate() |

## Spec Updates

The v0.2.0 specification (`.agents/specs/v0.2.0-authlm.md`) was updated with a "Prerequisite: v0.1.x Architecture Refactors" section documenting the six architecture changes (A1–A6) identified in the audit. These are tracked in the spec, not in a separate plan file, since v0.2.0 work is not scheduled yet.
