from __future__ import annotations

from enum import StrEnum

import click

from authlm.cli import _context
from authlm.credentials import ApiKeyCredential, OAuthCredential
from authlm.stores.base import CredentialStore


class EnvFormat(StrEnum):
    SHELL = "shell"
    DOCKER = "docker"
    GITHUB = "github"


def _format_shell(lines: list[tuple[str, str]]) -> str:
    return "\n".join(f"{k}={v}" for k, v in lines) + "\n"


def _format_github(lines: list[tuple[str, str]]) -> str:
    return "\n".join(f"{k}: ${{{{ secrets.{k} }}}}" for k, _ in lines) + "\n"


_FORMATTERS = {
    EnvFormat.SHELL: _format_shell,
    EnvFormat.DOCKER: _format_shell,
    EnvFormat.GITHUB: _format_github,
}


def _credential_to_env_vars(
    cred: ApiKeyCredential | OAuthCredential,
) -> list[tuple[str, str]]:
    prefix = cred.provider.upper()
    if isinstance(cred, ApiKeyCredential):
        return [(f"{prefix}_API_KEY", cred.secret)]
    out: list[tuple[str, str]] = [(f"{prefix}_ACCESS_TOKEN", cred.access_token)]
    if cred.refresh_token:
        out.append((f"{prefix}_REFRESH_TOKEN", cred.refresh_token))
    return out


@click.command("env")
@click.argument("provider_id")
@click.option("--alias", default="default", show_default=True)
@click.option(
    "--export-format",
    "fmt",
    type=click.Choice([f.value for f in EnvFormat]),
    default=EnvFormat.SHELL.value,
    show_default=True,
    help="Output format: shell (eval), docker (--env-file), github (workflow env).",
)
@click.option(
    "--store",
    "store_name",
    default=None,
    type=click.Choice(["keyring", "encrypted_file", "env", "memory"]),
    help="Credential store backend (env: AUTHLM_STORE).",
)
def env(
    provider_id: str,
    alias: str,
    fmt: str,
    store_name: str | None,
) -> None:
    """Export credential as shell env vars.

    Designed for use in shell: eval "$(authlm env openai)".
    """
    store: CredentialStore = _context.get_store(store_name=store_name)
    cred = store.get(provider_id, alias)
    if cred is None:
        raise click.ClickException(f"Credential not found for {provider_id}:{alias}")
    pairs = _credential_to_env_vars(cred)  # type: ignore[arg-type]
    formatter = _FORMATTERS[EnvFormat(fmt)]
    click.echo(formatter(pairs), nl=False)
