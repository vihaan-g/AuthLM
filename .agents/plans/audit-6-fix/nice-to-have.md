# Nice-to-Have Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship low-effort code quality and maintainability improvements that were deferred from the v0.1.0 release review. None of these block any release — they're pure DX and code health.

**Architecture:** Ten independent tasks. No shared state. Run in any order, ship in any future release.

**Tech Stack:** Python 3.11+, Pydantic, httpx, click, ruff, mypy

**Source:** `.agents/audits/v0.1.0-release-audit.md` (Nice-to-Have section)

## Global Constraints

- `from __future__ import annotations` at the top of every file.
- Explicit type annotations on all function signatures and module-level variables.
- No bare `except:`. No `except Exception: pass`. Catch specific exceptions.
- No `print()` calls in library code.
- Run `uv run ruff check . && uv run ruff format . && uv run mypy src/authlm && uv run pytest` before each commit.

---

### Task 1: Extract Shared Store-Resolution Pattern from CLI Files

**Files:**
- Modify: `src/authlm/cli/_context.py`
- Modify: `src/authlm/cli/connect.py`
- Modify: `src/authlm/cli/disconnect.py`
- Modify: `src/authlm/cli/status.py`
- Modify: `src/authlm/cli/env.py`
- Modify: `src/authlm/cli/list_cmd.py`

**Steps:**

- [ ] **Step 1: Add `resolve_store()` helper to `_context.py`**

```python
from authlm.stores import build_store, get_default_store
from authlm.stores.base import CredentialStore


def resolve_store(store_name: str | None) -> CredentialStore:
    """Resolve a CredentialStore from a store name or the default.

    Args:
        store_name: One of ``"keyring"``, ``"encrypted_file"``, ``"env"``,
            ``"memory"``, or ``None`` for auto-selection.

    Returns:
        A CredentialStore instance.
    """
    if store_name is None:
        return get_default_store()
    return build_store(store_name=store_name)
```

- [ ] **Step 2: Replace the 5 duplicate blocks**

In each of the five CLI command files, replace:

```python
if store_name is None:
    store = get_default_store()
else:
    store = build_store(store_name=store_name)
```

With:

```python
from authlm.cli._context import resolve_store  # if not already imported

store = resolve_store(store_name)
```

- [ ] **Step 3: Remove the now-unused imports of `build_store` and `get_default_store` from each CLI file**

Each file imports `from authlm.stores import build_store, get_default_store`. Remove that import line from all five files (they now get it transitively through `_context.py` — or keep it if there's a lint rule requiring explicit imports).

- [ ] **Step 4: Run CLI tests**

```bash
uv run pytest tests/unit/test_cli_connect.py tests/unit/test_cli_disconnect.py tests/unit/test_cli_status.py tests/unit/test_cli_env.py tests/unit/test_cli_list.py -v
```

Expected: All pass.

- [ ] **Step 5: Run full check and commit**

```bash
uv run ruff check . && uv run mypy src/authlm && uv run pytest
git add src/authlm/cli/
git commit -S -F - <<'EOF'
refactor(cli): extract store-resolution pattern into _context.resolve_store()

Four-line block (if/else on store_name) was duplicated five times.
Single helper in _context.py replaces all five instances.
EOF
```

---

### Task 2: Add TypedDict Definitions for OAuth Responses

**Files:**
- Create: `src/authlm/connection_methods/_oauth_types.py`
- Modify: `src/authlm/connection_methods/_oauth_helpers.py`
- Modify: `src/authlm/connection_methods/oauth_device.py`

**Steps:**

- [ ] **Step 1: Create `_oauth_types.py`**

```python
from __future__ import annotations

from typing import TypedDict


class DeviceCodeResponse(TypedDict):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int | None


class TokenResponse(TypedDict, total=False):
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str
    token_type: str
```

- [ ] **Step 2: Update `build_oauth_credential` signature**

In `_oauth_helpers.py`, change the signature from:

```python
def build_oauth_credential(
    *,
    data: dict[str, Any],
    ...
```

To:

```python
def build_oauth_credential(
    *,
    data: TokenResponse,
    ...
```

And remove `from typing import Any` if it's no longer needed elsewhere.

- [ ] **Step 3: Update `_request_device_code` and `_poll_for_token` return types**

In `oauth_device.py`, change return type annotations from `dict[str, Any]` to `DeviceCodeResponse` and `TokenResponse` respectively.

- [ ] **Step 4: Run checks and commit**

```bash
uv run ruff check . && uv run mypy src/authlm && uv run pytest
git add src/authlm/connection_methods/
git commit -S -m "refactor: add TypedDict for OAuth response JSON payloads"
```

---

### Task 3: Add `DEFAULT_REFRESH_MARGIN` Constant

**Files:**
- Modify: `src/authlm/api.py`
- Modify: `src/authlm/__init__.py`

**Steps:**

- [ ] **Step 1: Add constant to `api.py`**

```python
DEFAULT_REFRESH_MARGIN = timedelta(minutes=5)
```

- [ ] **Step 2: Re-export from `__init__.py`**

Add `DEFAULT_REFRESH_MARGIN` to the imports and `__all__` list.

- [ ] **Step 3: Run checks and commit**

```bash
uv run pytest && uv run mypy src/authlm
git add src/authlm/api.py src/authlm/__init__.py
git commit -S -m "feat: add DEFAULT_REFRESH_MARGIN constant (5 minutes)"
```

---

### Task 4: Add Pydantic `Field(description=...)` on Models

**Files:**
- Modify: `src/authlm/credentials.py`
- Modify: `src/authlm/metadata.py`

**Steps:**

- [ ] **Step 1: Add descriptions to `credential.py` fields**

```python
class Credential(BaseModel):
    provider: str = Field(description="Stable provider identifier, e.g. 'openai'.")
    alias: str = Field(description="Label for this credential, e.g. 'default' or 'work'.")
    method_id: str = Field(description="Connection method used, e.g. 'api_key'.")
    warning_acknowledged_at: datetime | None = Field(
        default=None,
        description="When the user confirmed the connection-method warning, if any.",
    )

class ApiKeyCredential(Credential):
    type: Literal["api_key"] = "api_key"
    secret: str = Field(repr=False, description="The API key string.")

class OAuthCredential(Credential):
    type: Literal["oauth"] = "oauth"
    access_token: str = Field(repr=False, description="OAuth access token.")
    refresh_token: str | None = Field(
        default=None,
        repr=False,
        description="OAuth refresh token. None for providers that don't issue one.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="UTC-aware expiry timestamp. None if no expiry is known.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="OAuth scopes granted by the authorization server.",
    )
    client_id: str | None = Field(
        default=None,
        description="OAuth client ID used. Set for refresh-token-rotation providers.",
    )
```

- [ ] **Step 2: Add descriptions to `metadata.py` fields**

```python
class MetadataEntry(BaseModel):
    provider_display_name: str = Field(description="Human-readable provider name.")
    method_id: str = Field(description="Connection method ID used to obtain this credential.")
    connected_at: datetime = Field(description="When this credential was first connected.")
    last_validated_at: datetime | None = Field(default=None, description="When the credential was last confirmed working via validate().")
    warning_acknowledged_at: datetime | None = Field(default=None, description="When the user acknowledged the method warning, if any.")
    scopes: list[str] = Field(default_factory=list, description="OAuth scopes (empty for API key credentials).")
    client_id: str | None = Field(default=None, description="OAuth client ID used (for diagnostics).")
    fingerprint: str | None = Field(default=None, description="Truncated SHA-256 of the secret for change detection — never the secret itself.")
```

- [ ] **Step 3: Run checks and commit**

```bash
uv run pytest && uv run mypy src/authlm
git add src/authlm/credentials.py src/authlm/metadata.py
git commit -S -m "docs: add Pydantic Field descriptions to credential and metadata models"
```

---

### Task 5: Add mtime-Based Cache to `MetadataStore._read()`

**Files:**
- Modify: `src/authlm/metadata.py`

**Steps:**

- [ ] **Step 1: Add cache field and update `_read()`**

In `MetadataStore.__init__`, add:

```python
self._cache: tuple[float, dict[str, dict[str, dict[str, object]]]] | None = None
```

In `MetadataStore._read`, before the `if not self._path.exists()` check, add:

```python
def _read(self) -> dict[str, dict[str, dict[str, object]]]:
    mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
    if self._cache is not None and self._cache[0] == mtime:
        return self._cache[1]
    ...
    # After building the data dict, before returning:
    self._cache = (mtime, data)
    return data
```

- [ ] **Step 2: Invalidate cache on write and delete**

In `_write` and `delete`, add `self._cache = None` before the write/delete operation.

- [ ] **Step 3: Run checks and commit**

```bash
uv run pytest tests/unit/test_metadata.py -v && uv run mypy src/authlm
git add src/authlm/metadata.py
git commit -S -m "perf: add mtime-based cache to MetadataStore._read()"
```

---

### Task 6: Replace `assert oauth is not None` with Explicit Error

**Files:**
- Modify: `src/authlm/providers/openai.py`
- Modify: `src/authlm/providers/anthropic.py`
- Modify: `src/authlm/providers/google.py`

**Steps:**

- [ ] **Step 1: Replace in each provider**

In `openai.py`, change:

```python
oauth = get_oauth_config("openai")
assert oauth is not None
```

To:

```python
oauth = get_oauth_config("openai")
if oauth is None:
    raise AuthLMError("OpenAI provider has no OAuth config — this is a bug in authlm.")
```

Repeat for `anthropic.py` and `google.py` with the appropriate provider name. Add `from authlm.errors import AuthLMError` if not already imported.

- [ ] **Step 2: Run checks and commit**

```bash
uv run pytest tests/unit/test_providers_openai.py tests/unit/test_providers_anthropic.py tests/unit/test_providers_google.py -v
uv run mypy src/authlm
git add src/authlm/providers/openai.py src/authlm/providers/anthropic.py src/authlm/providers/google.py
git commit -S -m "fix: replace assert with explicit AuthLMError in provider OAuth config checks"
```

---

### Task 7: Add `__version_tuple__`

**Files:**
- Modify: `src/authlm/_version.py`
- Modify: `src/authlm/__init__.py`

**Steps:**

- [ ] **Step 1: Add tuple to `_version.py`**

```python
from __future__ import annotations

__version__: str = "0.1.0"
__version_tuple__: tuple[int, int, int] = (0, 1, 0)
```

- [ ] **Step 2: Re-export from `__init__.py`**

Add `from authlm._version import __version_tuple__ as __version_tuple__` and add `"__version_tuple__"` to `__all__`.

- [ ] **Step 3: Run checks and commit**

```bash
uv run python -c "import authlm; print(authlm.__version_tuple__)"
# Expected: (0, 1, 0)
uv run pytest
git add src/authlm/_version.py src/authlm/__init__.py
git commit -S -m "feat: add __version_tuple__ for programmatic version comparison"
```

---

### Task 8: Merge Two `model_copy()` Calls in `api.connect()`

**Files:**
- Modify: `src/authlm/api.py`

**Steps:**

- [ ] **Step 1: Merge the two copies**

Find the block:

```python
if cred.alias != alias:
    cred = cred.model_copy(update={"alias": alias})
if method.warning:
    cred = cred.model_copy(update={"warning_acknowledged_at": datetime.now(UTC)})
```

Replace with:

```python
updates: dict[str, object] = {}
if cred.alias != alias:
    updates["alias"] = alias
if method.warning:
    updates["warning_acknowledged_at"] = datetime.now(UTC)
if updates:
    cred = cred.model_copy(update=updates)
```

- [ ] **Step 2: Run checks and commit**

```bash
uv run pytest tests/unit/test_api.py -v && uv run mypy src/authlm
git add src/authlm/api.py
git commit -S -m "refactor: merge two model_copy calls in api.connect()"
```

---

### Task 9: Add `get_user_data_path()` to Top-Level `__all__`

**Files:**
- Modify: `src/authlm/__init__.py`

**Steps:**

- [ ] **Step 1: Add import and export**

Add to imports:

```python
from authlm.stores import get_user_data_path
```

Add `"get_user_data_path"` to `__all__`.

- [ ] **Step 2: Run checks and commit**

```bash
uv run python -c "import authlm; print(authlm.get_user_data_path())"
uv run pytest
git add src/authlm/__init__.py
git commit -S -m "feat: export get_user_data_path from top-level authlm package"
```

---

### Task 10: Normalize `validate()` Docstring to Google Style

**Files:**
- Modify: `src/authlm/validation.py`

**Steps:**

- [ ] **Step 1: Rewrite the docstring**

Replace the current inline-prose docstring with:

```python
async def validate(
    cred: Credential,
    *,
    force: bool,
) -> bool:
    """Probe whether a credential is currently usable.

    Makes a lightweight API call (e.g. ``GET /v1/models``) to the
    provider's validation URL. Returns ``True`` if the credential works,
    ``False`` if it doesn't.

    Args:
        cred: The credential to validate.
        force: If ``True``, bypass the warned-method refusal check.
            Methods with a warning (e.g. Anthropic Claude Pro OAuth)
            are refused unless ``force=True``.

    Returns:
        ``True`` on 2xx, ``False`` on 401/404.

    Raises:
        PermissionError: If the method has a warning and ``force=False``.
        AccessDenied: If the token works but the user lacks access (403).
        TokenEndpointError: On other 4xx errors from the provider.
        RefreshFailed: On network errors or 5xx from the provider.
    """
```

- [ ] **Step 2: Commit**

```bash
git add src/authlm/validation.py
git commit -S -m "docs: normalize validate() docstring to Google-style Args/Returns/Raises"
```
