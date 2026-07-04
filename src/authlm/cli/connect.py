from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import cast

import click

from authlm import api as _api
from authlm.cli import _context
from authlm.errors import AuthLMError
from authlm.providers.base import ConnectionMethod
from authlm.providers.registry import get_provider


def _secret_prompt() -> Callable[[str], str]:
    """Return a Click-aware secret prompt."""

    def _ask(prompt: str) -> str:
        response = click.prompt(prompt, hide_input=True, confirmation_prompt=False)
        return cast(str, response)

    return _ask


def _on_prompt() -> Callable[[str, str], None]:
    """Return a Click-aware device-code prompt (prints to stderr)."""

    def _show(uri: str, code: str) -> None:
        click.echo(f"Open {uri} and enter code: {code}", err=True)

    return _show


def _open_browser() -> Callable[[str], None]:
    """Return a Click-aware PKCE browser opener (logs URL to stderr)."""

    def _open(url: str) -> None:
        click.echo(f"Opening browser: {url[:80]}...", err=True)
        webbrowser.open(url)

    return _open


@click.command("connect")
@click.argument("provider_id")
@click.option("--alias", default="default", show_default=True, help="Credential alias.")
@click.option(
    "--method",
    "method_id",
    default=None,
    help="Connection method ID. If omitted, an interactive picker is shown.",
)
@click.option(
    "--include-warned",
    is_flag=True,
    default=False,
    help="Include warned methods (e.g. Anthropic Claude Pro) in the picker.",
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
    help=(
        "Path to metadata.json "
        "(default: platform user data dir, env: AUTHLM_METADATA_PATH)."
    ),
)
def connect(
    provider_id: str,
    alias: str,
    method_id: str | None,
    include_warned: bool,
    store_name: str | None,
    metadata_path: Path | None,
) -> None:
    """Connect a provider interactively."""
    try:
        provider = get_provider(provider_id)
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc

    methods = list(provider.connection_methods(include_warned=include_warned))
    available_ids = {m.id for m in methods}

    chosen: ConnectionMethod | None = None
    if method_id is not None:
        if method_id not in available_ids:
            if include_warned:
                raise click.ClickException(
                    f"Unknown method {method_id!r} for provider {provider_id!r}"
                )
            raise click.ClickException(
                f"Method {method_id!r} is not available without --include-warned. "
                "Pass --include-warned to use warned methods."
            )
        chosen = next(m for m in methods if m.id == method_id)
    else:
        if not _context.is_tty():
            raise click.ClickException(
                "Interactive method selection requires a TTY. "
                "Pass --method <id> to select a method non-interactively."
            )
        chosen = _pick_method(methods, provider_id=provider_id)

    if chosen.warning is not None:
        click.echo(f"\nWARNING: {chosen.warning}\n", err=True)
        if not click.confirm("Continue?", default=False):
            raise click.Abort()

    store = _context.get_store(store_name=store_name)
    meta = _context.get_metadata_store(metadata_path)

    try:
        cred = asyncio.run(
            _api.connect(
                provider_id,
                alias=alias,
                method=chosen,
                store=store,
                secret_prompt=_secret_prompt() if chosen.id == "api_key" else None,
                on_prompt=_on_prompt() if chosen.id == "oauth_device" else None,
                open_browser=_open_browser() if chosen.id == "oauth_browser" else None,
                metadata_store=meta,
            )
        )
    except AuthLMError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Connected {cred.provider}:{cred.alias} via {cred.method_id}")


def _pick_method(
    methods: list[ConnectionMethod], *, provider_id: str
) -> ConnectionMethod:
    click.echo(f"Available methods for {provider_id}:")
    for i, m in enumerate(methods, start=1):
        label = f"{i}. {m.label}"
        if m.warning is not None:
            label += "  (WARNED)"
        click.echo(f"  {label}")
    raw = click.prompt("Method", default="1", type=click.IntRange(1, len(methods)))
    return cast(ConnectionMethod, methods[raw - 1])
