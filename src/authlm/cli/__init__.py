from __future__ import annotations

import logging

import click

from authlm.cli import connect as _connect
from authlm.cli import list_cmd as _list_cmd
from authlm.cli import status as _status


@click.group()
def cli() -> None:
    """AuthLM credential manager."""
    logging.getLogger("authlm").setLevel(logging.WARNING)


cli.add_command(_list_cmd.list_cmd)
cli.add_command(_connect.connect)
cli.add_command(_status.status)


__all__ = ["cli"]
