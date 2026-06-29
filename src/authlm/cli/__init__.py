from __future__ import annotations

import logging

import click

from authlm.cli import connect as _connect
from authlm.cli import list_cmd as _list_cmd


@click.group()
def cli() -> None:
    """AuthLM credential manager."""
    logging.getLogger("authlm").setLevel(logging.WARNING)


cli.add_command(_list_cmd.list_cmd)
cli.add_command(_connect.connect)


__all__ = ["cli"]
