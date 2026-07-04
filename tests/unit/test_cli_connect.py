from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from authlm.cli import _context, cli
from authlm.credentials import OAuthCredential
from authlm.providers.anthropic import AnthropicProvider
from authlm.providers.base import ConnectionMethod, OAuthGrant
from authlm.stores import MemoryStore


def _patch_context_store(monkeypatch: pytest.MonkeyPatch, store: MemoryStore) -> None:
    monkeypatch.setattr(_context, "get_store", lambda *, store_name: store)


class _StubWarnedMethod:
    """A ConnectionMethod stub for the warned OAuth flow (no browser/network)."""

    @property
    def id(self) -> str:
        return "claude_pro_oauth_browser"

    @property
    def label(self) -> str:
        return "Claude Pro (browser)"

    @property
    def warning(self) -> str | None:
        return "Anthropic prohibits this in their ToS."

    @property
    def oauth_grant(self) -> OAuthGrant | None:
        return OAuthGrant.AUTHORIZATION_CODE_PKCE

    async def connect(self, *, store: Any) -> OAuthCredential:
        return OAuthCredential(
            provider="anthropic",
            alias="default",
            method_id="claude_pro_oauth_browser",
            access_token="A",
            refresh_token="R",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    async def validate(self, cred: Any, *, force: bool) -> bool:
        return True


def _patch_anthropic_methods(
    monkeypatch: pytest.MonkeyPatch, methods: Sequence[ConnectionMethod]
) -> None:
    """Replace AnthropicProvider.connection_methods to return the given list."""
    monkeypatch.setattr(
        AnthropicProvider,
        "connection_methods",
        lambda self, *, include_warned: list(methods),
    )


def test_connect_unknown_provider(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_context_store(monkeypatch, MemoryStore())
    result = runner.invoke(
        cli,
        [
            "connect",
            "nonexistent",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code != 0
    assert "Unknown provider" in result.output


def test_connect_api_key_with_method(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real OpenRouterProvider, real APIKeyMethod; secret_prompt reads from input."""
    store = MemoryStore()
    _patch_context_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        [
            "connect",
            "openrouter",
            "--method",
            "api_key",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="sk-or-test\n",
    )
    assert result.exit_code == 0, result.output
    assert "Connected openrouter:default" in result.output
    assert store.get("openrouter", "default") is not None


def test_connect_api_key_empty_rejected(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty key on stdin is rejected by the real APIKeyMethod."""
    _patch_context_store(monkeypatch, MemoryStore())
    result = runner.invoke(
        cli,
        [
            "connect",
            "openrouter",
            "--method",
            "api_key",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="\n",
    )
    assert result.exit_code != 0, result.output
    assert "empty" in result.output.lower() or "api key" in result.output.lower()


def test_connect_default_alias(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The --alias flag re-keys the stored credential."""
    store = MemoryStore()
    _patch_context_store(monkeypatch, store)
    result = runner.invoke(
        cli,
        [
            "connect",
            "openai",
            "--alias",
            "work",
            "--method",
            "api_key",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="sk-w\n",
    )
    assert result.exit_code == 0, result.output
    cred = store.get("openai", "work")
    assert cred is not None


def test_connect_interactive_picks_method(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --method, the CLI shows the picker and the user selects 1 (api_key)."""
    store = MemoryStore()
    _patch_context_store(monkeypatch, store)
    monkeypatch.setattr(_context, "is_tty", lambda: True)
    result = runner.invoke(
        cli,
        [
            "connect",
            "openai",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="1\nsk-test\n",
    )
    assert result.exit_code == 0, result.output
    cred = store.get("openai", "default")
    assert cred is not None


def test_connect_non_tty_without_method_refuses(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_context_store(monkeypatch, MemoryStore())
    monkeypatch.setattr(_context, "is_tty", lambda: False)
    result = runner.invoke(
        cli,
        [
            "connect",
            "openai",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="1\nsk-test\n",
    )
    assert result.exit_code != 0
    assert "--method" in result.output or "method" in result.output.lower()


def test_connect_warned_method_requires_include_warned(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_context_store(monkeypatch, MemoryStore())
    result = runner.invoke(
        cli,
        [
            "connect",
            "anthropic",
            "--method",
            "claude_pro_oauth_browser",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
    )
    assert result.exit_code != 0
    assert "--include-warned" in result.output or "include-warned" in result.output


def test_connect_warned_method_confirmed(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With --include-warned and a 'y' confirmation, the connect succeeds."""
    store = MemoryStore()
    _patch_context_store(monkeypatch, store)
    _patch_anthropic_methods(monkeypatch, [_StubWarnedMethod()])
    result = runner.invoke(
        cli,
        [
            "connect",
            "anthropic",
            "--method",
            "claude_pro_oauth_browser",
            "--include-warned",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert "Connected anthropic:default" in result.output


def test_connect_warned_method_declined(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With --include-warned but a 'n' confirmation, the connect is aborted."""
    _patch_context_store(monkeypatch, MemoryStore())
    _patch_anthropic_methods(monkeypatch, [_StubWarnedMethod()])
    result = runner.invoke(
        cli,
        [
            "connect",
            "anthropic",
            "--method",
            "claude_pro_oauth_browser",
            "--include-warned",
            "--store",
            "memory",
            "--metadata-path",
            str(tmp_path / "m.json"),
        ],
        input="n\n",
    )
    assert result.exit_code != 0
    assert "Aborted" in result.output or "declined" in result.output.lower()


def test_get_metadata_path_returns_default(tmp_path: Path) -> None:
    """get_metadata_path(None) resolves to a metadata.json path."""
    from authlm.cli._context import get_metadata_path

    path = get_metadata_path(None)
    assert path.name == "metadata.json"


def test_get_metadata_path_respects_override(tmp_path: Path) -> None:
    """get_metadata_path with explicit path returns that path."""
    from authlm.cli._context import get_metadata_path

    custom = tmp_path / "custom" / "meta.json"
    path = get_metadata_path(custom)
    assert path == custom
