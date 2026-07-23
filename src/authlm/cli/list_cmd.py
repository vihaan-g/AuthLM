from __future__ import annotations

from pathlib import Path

import click

from authlm.cli._context import get_metadata_path
from authlm.cli._formatters import format_list_json, format_list_table
from authlm.errors import AuthLMError
from authlm.metadata import MetadataStore
from authlm.stores import build_store, get_default_store


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
    try:
        if store_name is None:
            store = get_default_store()
        else:
            store = build_store(store_name=store_name)
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        entries = sorted(
            (provider, alias, cred.method_id if cred is not None else "")
            for provider, alias in store.list()
            for cred in [store.get(provider, alias)]
        )
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    metadata_store = MetadataStore(path=get_metadata_path(metadata_path))
    if json_format or output_format == "json":
        formatter = format_list_json
    else:
        formatter = format_list_table
    click.echo(
        formatter(
            entries,
            backend_name=store.backend_name(),
            metadata_store=metadata_store,
        )
    )
