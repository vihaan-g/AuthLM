from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import click

from authlm._version import __version__
from authlm.cli._context import get_metadata_path
from authlm.credentials import ApiKeyCredential, OAuthCredential, compute_fingerprint
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
        store = (
            get_default_store()
            if store_name is None
            else build_store(store_name=store_name)
        )
        click.echo(f"  Store Backend: {store.backend_name()}")
        click.echo("  Status:        OK")
    except AuthLMError as exc:
        click.echo(f"  Status:        ERROR ({exc})")
        return

    # 4. Metadata File inspection
    resolved_meta_path = get_metadata_path(metadata_path)
    click.echo("\n[Metadata Store]")
    click.echo(f"  Metadata Path: {resolved_meta_path}")
    if resolved_meta_path.exists():
        click.echo("  Status:        Present")
        if sys.platform != "win32":
            mode_oct = oct(resolved_meta_path.stat().st_mode & 0o777)
            click.echo(f"  Permissions:   {mode_oct}")
    else:
        click.echo("  Status:        Not created yet")

    # 5. Stored Credentials & Fingerprint Integrity
    click.echo("\n[Stored Credentials]")
    meta_store = MetadataStore(path=resolved_meta_path)
    try:
        pairs = store.list()
        if not pairs:
            click.echo("  No credentials stored.")
        else:
            mismatches = 0
            for provider, alias in sorted(pairs):
                cred = store.get(provider, alias)
                meta = meta_store.get(provider, alias)
                if cred is None:
                    continue
                fp_status = "No metadata"
                secret: str | None = None
                if isinstance(cred, ApiKeyCredential):
                    secret = cred.secret
                elif isinstance(cred, OAuthCredential):
                    secret = cred.access_token

                if (
                    secret is not None
                    and meta is not None
                    and meta.fingerprint is not None
                ):
                    calc_fp = compute_fingerprint(secret)
                    if calc_fp == meta.fingerprint:
                        fp_status = "OK (fingerprint match)"
                    else:
                        fp_status = "WARNING (fingerprint mismatch!)"
                        mismatches += 1

                click.echo(f"  - {provider}:{alias} [{cred.method_id}] -> {fp_status}")
            if mismatches > 0:
                click.echo(
                    f"\n  WARNING: {mismatches} credential(s) "
                    "show fingerprint mismatch!"
                )
    except AuthLMError as exc:
        click.echo(f"  Error reading stored credentials: {exc}")

    click.echo("\nDiagnostics complete.")
