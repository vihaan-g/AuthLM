from __future__ import annotations

from pathlib import Path

import click

from authlm.cli._context import get_metadata_path
from authlm.errors import AuthLMError
from authlm.metadata import MetadataStore
from authlm.stores import build_store, get_default_store


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
    try:
        if store_name is None:
            store = get_default_store()
        else:
            store = build_store(store_name=store_name)
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    meta = MetadataStore(path=get_metadata_path(metadata_path))
    try:
        cred = store.get(provider_id, alias)
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    if cred is None:
        raise click.ClickException(f"Credential not found for {provider_id}:{alias}")
    if not yes and not click.confirm(
        f"Delete {provider_id}:{alias}? This cannot be undone.",
        default=False,
    ):
        click.echo("Aborted.")
        return
    try:
        store.delete(provider_id, alias)
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    meta.delete(provider_id, alias)
    click.echo(f"Deleted {provider_id}:{alias}")
