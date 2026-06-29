from __future__ import annotations

from pathlib import Path

import click

from authlm.cli import _context
from authlm.cli._formatters import format_list_table
from authlm.metadata import MetadataStore
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
    help="Path to the metadata.json file (env: AUTHLM_METADATA_PATH).",
)
def list_cmd(store_name: str | None, metadata_path: Path | None) -> None:
    """List stored credentials."""
    store: CredentialStore = _context.get_store(store_name=store_name)
    entries = sorted(
        (provider, alias, _method_id(store, provider, alias))
        for provider, alias in store.list()
    )
    metadata_store = (
        MetadataStore(path=metadata_path) if metadata_path is not None else None
    )
    click.echo(
        format_list_table(
            entries,
            backend_name=store.backend_name(),
            metadata_store=metadata_store,
        )
    )


def _method_id(store: CredentialStore, provider: str, alias: str) -> str:
    cred = store.get(provider, alias)
    return cred.method_id if cred is not None else ""
