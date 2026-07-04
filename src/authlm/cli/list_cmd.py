from __future__ import annotations

from pathlib import Path

import click

from authlm.cli import _context
from authlm.cli._formatters import format_list_table
from authlm.stores.base import CredentialStore


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
    help="Path to metadata.json (default: ~/.local/share/authlm/metadata.json, env: AUTHLM_METADATA_PATH).",
)
def list_cmd(store_name: str | None, metadata_path: Path | None) -> None:
    """List stored credentials."""
    store: CredentialStore = _context.get_store(store_name=store_name)
    entries = sorted(
        (provider, alias, cred.method_id if cred is not None else "")
        for provider, alias in store.list()
        for cred in [store.get(provider, alias)]
    )
    metadata_store = _context.get_metadata_store(metadata_path)
    click.echo(
        format_list_table(
            entries,
            backend_name=store.backend_name(),
            metadata_store=metadata_store,
        )
    )
