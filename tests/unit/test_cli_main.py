from __future__ import annotations

from click.testing import CliRunner

import authlm.cli as cli_pkg
from authlm.cli import cli


def test_no_args_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    for cmd in ("connect", "list", "status", "disconnect", "env"):
        assert cmd in result.output


def test_help_flag(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ("connect", "list", "status", "disconnect", "env"):
        assert cmd in result.output


def test_group_name_is_cli() -> None:
    assert cli.name == "cli"


def test_entry_point_is_importable() -> None:
    """The pyproject.toml [project.scripts] entry is `authlm.cli:cli`."""
    assert hasattr(cli_pkg, "cli")
    assert cli_pkg.cli is cli


def test_invalid_store_name_displays_clean_error(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["list", "--store", "invalid_store_backend"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Unknown store" in result.output or "invalid_store_backend" in result.output
