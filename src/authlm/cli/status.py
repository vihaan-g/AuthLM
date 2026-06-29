from __future__ import annotations

import asyncio
from pathlib import Path

import click

from authlm import api as _api
from authlm.cli import _context
from authlm.cli._formatters import format_status_table
from authlm.errors import AuthLMError
from authlm.metadata import MetadataStore
from authlm.stores.base import CredentialStore
from authlm.validation import _is_warned


@click.command("status")
@click.argument("provider_id", required=False)
@click.option("--alias", default="default", show_default=True)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Show all aliases for the given provider.",
)
@click.option(
    "--validate",
    "do_validate",
    is_flag=True,
    default=False,
    help="Probe each credential against the provider's validation URL.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Allow validation of warned methods (Anthropic Claude Pro).",
)
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
def status(
    provider_id: str | None,
    alias: str,
    show_all: bool,
    do_validate: bool,
    force: bool,
    store_name: str | None,
    metadata_path: Path | None,
) -> None:
    """Show credential metadata; --validate to probe."""
    store: CredentialStore = _context.get_store(store_name=store_name)
    meta = MetadataStore(path=metadata_path) if metadata_path is not None else None
    pairs: list[tuple[str, str]]
    if provider_id is None:
        pairs = sorted(store.list())
    else:
        if show_all:
            pairs = [(p, a) for p, a in store.list() if p == provider_id]
        else:
            pairs = [(provider_id, alias)]
    if not pairs:
        click.echo("No credentials stored.", err=True)
        return
    for provider, a in pairs:
        cred = store.get(provider, a)
        if cred is None:
            raise click.ClickException(f"{provider}:{a}: not found")
        metadata = meta.get(provider, a) if meta is not None else None
        click.echo(
            format_status_table(cred, metadata, backend_name=store.backend_name())
        )
        if do_validate:
            if force and _is_warned(cred.method_id):
                click.echo(
                    "WARNING: probing a warned method; this call may be "
                    "detectable by the provider.",
                    err=True,
                )
            try:
                result = asyncio.run(_api.validate(cred, force=force))
            except (AuthLMError, PermissionError) as exc:
                raise click.ClickException(str(exc)) from exc
            click.echo(f"Validation: {'Valid' if result else 'Invalid'}")
