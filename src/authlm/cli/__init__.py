from __future__ import annotations

import logging

import click

from authlm.cli import connect as _connect
from authlm.cli import disconnect as _disconnect
from authlm.cli import env as _env
from authlm.cli import list_cmd as _list_cmd
from authlm.cli import status as _status


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AuthLM credential manager."""
    logging.getLogger("authlm").setLevel(logging.WARNING)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(_list_cmd.list_cmd)
cli.add_command(_connect.connect)
cli.add_command(_status.status)
cli.add_command(_disconnect.disconnect)
cli.add_command(_env.env)


__all__ = ["cli"]
