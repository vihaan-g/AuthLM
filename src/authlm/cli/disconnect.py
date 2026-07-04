from __future__ import annotations

from pathlib import Path

import click

from authlm.cli import _context
from authlm.stores.base import CredentialStore


@click.command("disconnect")
@click.argument("provider_id")
@click.option("--alias", default="default", show_default=True)
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation.")
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
def disconnect(
    provider_id: str,
    alias: str,
    yes: bool,
    store_name: str | None,
    metadata_path: Path | None,
) -> None:
    """Delete a credential and its metadata entry."""
    store: CredentialStore = _context.get_store(store_name=store_name)
    meta = _context.get_metadata_store(metadata_path)
    cred = store.get(provider_id, alias)
    if cred is None:
        raise click.ClickException(f"Credential not found for {provider_id}:{alias}")
    if not yes and not click.confirm(
        f"Delete {provider_id}:{alias}? This cannot be undone.",
        default=False,
    ):
        click.echo("Aborted.")
        return
    store.delete(provider_id, alias)
    meta.delete(provider_id, alias)
    click.echo(f"Deleted {provider_id}:{alias}")
