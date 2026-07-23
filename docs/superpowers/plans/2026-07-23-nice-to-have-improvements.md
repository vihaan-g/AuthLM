# AuthLM Post-v0.1.0 Non-Blocking Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement non-blocking CLI enhancements for AuthLM: JSON format output for `authlm list` (`authlm list --json`) and a diagnostic health check command (`authlm doctor`).

**Architecture:** Extend `src/authlm/cli/_formatters.py` with `format_list_json()` and update `src/authlm/cli/list_cmd.py` to add `--json` and `--format` options. Create `src/authlm/cli/doctor.py` implementing `authlm doctor` to execute system environment, store backend, file permission, credential fingerprint, and config checks, registering it in `src/authlm/cli/__init__.py`.

**Tech Stack:** Python 3.11+, Click, Pydantic, standard library (`platform`, `sys`, `pathlib`, `json`).

## Global Constraints

- All Python files must start with `from __future__ import annotations`.
- Explicit type annotations required on all function signatures and module-level variables.
- Type checking (`uv run mypy src/authlm`) must pass with `--strict`.
- Linting (`uv run ruff check .`) and formatting (`uv run ruff format --check .`) must pass with zero issues.
- All unit tests (`uv run pytest`) must pass cleanly.
- Secrets must never be logged or formatted into non-redacted outputs.

---

### Task 1: Add `--json` Output Support to `authlm list`

**Files:**
- Modify: `src/authlm/cli/_formatters.py`
- Modify: `src/authlm/cli/list_cmd.py`
- Test: `tests/unit/test_cli_list.py`

**Interfaces:**
- Consumes: `MetadataStore`, `CredentialStore`
- Produces: `format_list_json(entries: list[tuple[str, str, str]], *, backend_name: str, metadata_store: MetadataStore | None = None) -> str`

- [ ] **Step 1: Write the failing test**

Edit `tests/unit/test_cli_list.py` to add a test for `--json` output:

```python
def test_list_cmd_json_output(runner: CliRunner, tmp_path: Path) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-test"
        )
    )
    meta_path = tmp_path / "metadata.json"
    set_store(store)
    try:
        result = runner.invoke(
            cli, ["list", "--json", "--metadata-path", str(meta_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["provider"] == "openai"
        assert data[0]["alias"] == "default"
        assert data[0]["method_id"] == "api_key"
        assert data[0]["backend"] == "Memory"
    finally:
        set_store(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_list.py::test_list_cmd_json_output -v`
Expected: FAIL with "No such option: --json" or similar error.

- [ ] **Step 3: Implement `format_list_json()` and update `list_cmd`**

In `src/authlm/cli/_formatters.py`:
```python
def format_list_json(
    entries: list[tuple[str, str, str]],
    *,
    backend_name: str,
    metadata_store: MetadataStore | None = None,
) -> str:
    """Render a `list`-style JSON string for the given credentials."""
    records: list[dict[str, str | None]] = []
    for provider, alias, method_id in entries:
        last_validated: str | None = None
        if metadata_store is not None:
            entry = metadata_store.get(provider, alias)
            if entry is not None and entry.last_validated_at is not None:
                last_validated = _format_datetime(entry.last_validated_at)
        records.append(
            {
                "provider": provider,
                "alias": alias,
                "method_id": method_id,
                "backend": backend_name,
                "last_validated": last_validated,
            }
        )
    return json.dumps(records, indent=2) + "\n"
```

In `src/authlm/cli/list_cmd.py`:
```python
@click.command("list")
@click.option(
    "--store",
    "store_name",
    default=None,
    type=click.Choice(["keyring", "encrypted_file", "env", "memory"]),
    help="Credential store backend (env: AUTHLM_STORE).",
)
@click.option(
    "--metadata-path",
    type=click.Path(dir_okay=False, path_type=Path),  # type: ignore[type-var]
    default=None,
    help=(
        "Path to metadata.json "
        "(default: platform user data dir, env: AUTHLM_METADATA_PATH)."
    ),
)
@click.option(
    "--json",
    "json_format",
    is_flag=True,
    default=False,
    help="Output records in JSON format.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (table or json).",
)
def list_cmd(
    store_name: str | None,
    metadata_path: Path | None,
    json_format: bool,
    output_format: str,
) -> None:
    """List stored credentials."""
    use_json = json_format or output_format == "json"
    # ... build entries and store ...
    metadata_store = MetadataStore(path=get_metadata_path(metadata_path))
    if use_json:
        click.echo(
            format_list_json(
                entries,
                backend_name=store.backend_name(),
                metadata_store=metadata_store,
            ),
            nl=False,
        )
    else:
        click.echo(
            format_list_table(
                entries,
                backend_name=store.backend_name(),
                metadata_store=metadata_store,
            )
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_list.py -v`
Expected: PASS

- [ ] **Step 5: Quality Gate & Commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/authlm && uv run pytest`
Commit:
```bash
git add src/authlm/cli/_formatters.py src/authlm/cli/list_cmd.py tests/unit/test_cli_list.py
git commit -m "feat(cli): add --json output option to authlm list command"
```

---

### Task 2: Implement `authlm doctor` Diagnostic Command

**Files:**
- Create: `src/authlm/cli/doctor.py`
- Modify: `src/authlm/cli/__init__.py`
- Test: `tests/unit/test_cli_doctor.py`

**Interfaces:**
- Consumes: `get_default_store()`, `get_metadata_path()`, `MetadataStore`, `compute_fingerprint()`
- Produces: `@click.command("doctor")` CLI command.

- [ ] **Step 1: Write failing test for `authlm doctor`**

Create `tests/unit/test_cli_doctor.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from authlm.cli import cli
from authlm.credentials import ApiKeyCredential
from authlm.stores import MemoryStore, set_store


def test_doctor_cmd_runs(runner: CliRunner, tmp_path: Path) -> None:
    store = MemoryStore()
    store.set(
        ApiKeyCredential(
            provider="openai", alias="default", method_id="api_key", secret="sk-test"
        )
    )
    meta_path = tmp_path / "metadata.json"
    set_store(store)
    try:
        result = runner.invoke(
            cli, ["doctor", "--metadata-path", str(meta_path)]
        )
        assert result.exit_code == 0
        assert "AuthLM System & Storage Diagnostics" in result.output
        assert "Store Backend:" in result.output
    finally:
        set_store(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_doctor.py`
Expected: FAIL with "No such command 'doctor'"

- [ ] **Step 3: Implement `src/authlm/cli/doctor.py` and register command**

Create `src/authlm/cli/doctor.py`:

```python
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import click

from authlm._version import __version__
from authlm.cli._context import get_metadata_path
from authlm.credentials import compute_fingerprint
from authlm.errors import AuthLMError
from authlm.metadata import MetadataStore
from authlm.stores import build_store, get_default_store


@click.command("doctor")
@click.option(
    "--store",
    "store_name",
    default=None,
    type=click.Choice(["keyring", "encrypted_file", "env", "memory"]),
    help="Credential store backend to inspect.",
)
@click.option(
    "--metadata-path",
    type=click.Path(dir_okay=False, path_type=Path),  # type: ignore[type-var]
    default=None,
    help="Path to metadata.json to inspect.",
)
def doctor(store_name: str | None, metadata_path: Path | None) -> None:
    """Run system diagnostics for AuthLM environment and credential stores."""
    click.echo(f"AuthLM System & Storage Diagnostics (v{__version__})")
    click.echo("=" * 50)
    
    # 1. Environment info
    click.echo(f"Python Version:  {sys.version.split()[0]} ({platform.platform()})")
    click.echo(f"Executable:      {sys.executable}")
    
    # 2. Environment variable overrides
    env_overrides: list[str] = []
    for var in (
        "AUTHLM_STORE",
        "AUTHLM_USER_PATH",
        "AUTHLM_METADATA_PATH",
        "AUTHLM_PASSPHRASE",
        "AUTHLM_OPENAI_CLIENT_ID",
        "AUTHLM_ANTHROPIC_CLIENT_ID",
        "AUTHLM_GOOGLE_CLIENT_ID",
    ):
        if var in os.environ:
            val = "[SET]" if "PASSPHRASE" in var else os.environ[var]
            env_overrides.append(f"{var}={val}")
    
    if env_overrides:
        click.echo("Env Overrides:   " + ", ".join(env_overrides))
    else:
        click.echo("Env Overrides:   None")
        
    # 3. Store Backend inspection
    click.echo("\n[Store Backend]")
    try:
        store = get_default_store() if store_name is None else build_store(store_name=store_name)
        click.echo(f"  Selected Store: {store.backend_name()}")
        click.echo("  Status:         OK")
    except AuthLMError as exc:
        click.echo(f"  Status:         ERROR ({exc})")
        return

    # 4. Metadata File inspection
    resolved_meta_path = get_metadata_path(metadata_path)
    click.echo("\n[Metadata Store]")
    click.echo(f"  Metadata Path:  {resolved_meta_path}")
    if resolved_meta_path.exists():
        click.echo("  Status:         Present")
        # Check permissions on POSIX
        if hasattr(os, "stat") and sys.platform != "win32":
            mode = oct(resolved_meta_path.stat().st_mode & 0o777)
            click.echo(f"  Permissions:    {mode}")
    else:
        click.echo("  Status:         Not created yet (will be created on first connect)")

    # 5. Stored Credentials & Fingerprint Integrity
    click.echo("\n[Stored Credentials]")
    meta_store = MetadataStore(path=resolved_meta_path)
    try:
        pairs = store.list()
        if not pairs:
            click.echo("  No credentials stored.")
        else:
            mismatches = 0
            for provider, alias in pairs:
                cred = store.get(provider, alias)
                meta = meta_store.get(provider, alias)
                if cred is None:
                    continue
                fp_status = "No metadata"
                if meta is not None and meta.fingerprint is not None:
                    calc_fp = compute_fingerprint(cred.get_secret())
                    if calc_fp == meta.fingerprint:
                        fp_status = "OK (fingerprint match)"
                    else:
                        fp_status = "WARNING (fingerprint mismatch!)"
                        mismatches += 1
                click.echo(f"  - {provider}:{alias} [{cred.method_id}] -> {fp_status}")
            if mismatches > 0:
                click.echo(f"\n  WARNING: {mismatches} credential(s) show fingerprint mismatch!")
    except AuthLMError as exc:
        click.echo(f"  Error reading stored credentials: {exc}")
    
    click.echo("\nDiagnostics complete.")
```

Update `src/authlm/cli/__init__.py`:
Import `doctor` module and add command `cli.add_command(_doctor.doctor)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_doctor.py -v`
Expected: PASS

- [ ] **Step 5: Quality Gate & Commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/authlm && uv run pytest`
Commit:
```bash
git add src/authlm/cli/doctor.py src/authlm/cli/__init__.py tests/unit/test_cli_doctor.py
git commit -m "feat(cli): add authlm doctor diagnostic command"
```
