from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from authlm.credentials import Credential
from authlm.metadata import MetadataEntry

if TYPE_CHECKING:
    from authlm.metadata import MetadataStore


def format_list_table(
    entries: list[tuple[str, str, str]],
    *,
    backend_name: str,
    metadata_store: MetadataStore | None = None,
) -> str:
    """Render a `list`-style ASCII table for the given credentials.

    ``entries`` is a list of ``(provider, alias, method_id)`` tuples. If
    ``metadata_store`` is provided, the last-validated column is populated
    from metadata; otherwise that column is blank.
    """
    if not entries:
        return "No credentials stored.\n"
    rows: list[tuple[str, str, str, str, str]] = []
    for provider, alias, method_id in entries:
        last_validated = ""
        if metadata_store is not None:
            entry = metadata_store.get(provider, alias)
            if entry is not None and entry.last_validated_at is not None:
                last_validated = _format_datetime(entry.last_validated_at)
        rows.append((provider, alias, method_id, backend_name, last_validated))

    header = ("PROVIDER", "ALIAS", "METHOD", "BACKEND", "LAST VALIDATED")
    widths = [
        max(_display_width(header[i]), *(len(row[i]) for row in rows)) for i in range(5)
    ]
    sep = "-+-".join("-" * w for w in widths)
    lines = [
        " | ".join(header[i].ljust(widths[i]) for i in range(5)),
        sep,
    ]
    for row in rows:
        lines.append(" | ".join(row[i].ljust(widths[i]) for i in range(5)))
    return "\n".join(lines) + "\n"


def format_status_table(
    cred: Credential,
    metadata: MetadataEntry | None,
    *,
    backend_name: str,
) -> str:
    """Render a `status`-style multi-line block for one credential."""
    lines: list[str] = [
        f"Provider: {cred.provider}",
        f"Alias: {cred.alias}",
        f"Method: {cred.method_id}",
        f"Backend: {backend_name}",
    ]
    if metadata is not None:
        lines.append(f"Connected: {_format_datetime(metadata.connected_at)}")
        if metadata.last_validated_at is not None:
            lines.append(
                f"Last validated: {_format_datetime(metadata.last_validated_at)}"
            )
        if metadata.warning_acknowledged_at is not None:
            lines.append(
                "Warning acknowledged: "
                f"{_format_datetime(metadata.warning_acknowledged_at)}"
            )
        if metadata.scopes:
            lines.append(f"Scopes:    {', '.join(metadata.scopes)}")
    return "\n".join(lines) + "\n"


def _display_width(s: str) -> int:
    return len(s)


def _format_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.astimezone().isoformat()
