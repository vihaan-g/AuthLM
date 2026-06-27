#!/usr/bin/env python3
"""Refresh the vendored models.dev snapshot.

Fetches the combined provider+model catalog and provider-agnostic model
metadata from https://models.dev and writes them into the local vendored
copy at ``src/authlm/_vendor/models-dev-snapshot.json``.  Also fetches each
provider's SVG logo into ``src/authlm/_vendor/_logos/``.

If the network is unavailable, the existing vendored snapshot is left
unchanged and a non-zero exit code is returned.  The CI pipeline should
treat a non-zero exit from this script as a soft failure, not a build
break — the offline fallback is intentionally load-bearing.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT     = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "src" / "authlm" / "_vendor" / "models-dev-snapshot.json"
LOGO_DIR      = REPO_ROOT / "src" / "authlm" / "_vendor" / "_logos"

API_URL    = "https://models.dev/api.json"
MODELS_URL = "https://models.dev/models.json"
LOGO_TMPL  = "https://models.dev/logos/{provider}.svg"

TIMEOUT = 15  # seconds


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return resp.read()


def main() -> int:
    try:
        api    = fetch_json(API_URL)
        models = fetch_json(MODELS_URL)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: network refresh failed: {exc!r}", file=sys.stderr)
        print("Leaving existing snapshot untouched.", file=sys.stderr)
        return 1

    snapshot = {
        "_meta": {
            "description": "Vendored snapshot of https://models.dev. Refresh via scripts/refresh_models_dev.py.",
            "schema_version": 1,
            "fetched_at":   datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "endpoints":    [API_URL, MODELS_URL],
        },
        "api":    api,
        "models": models,
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Updated {SNAPSHOT_PATH.relative_to(REPO_ROOT)}")

    # Best-effort logo fetch; a missing logo is non-fatal.
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    fetched, failed = 0, []
    for prov in api:
        try:
            (LOGO_DIR / f"{prov}.svg").write_bytes(fetch_bytes(LOGO_TMPL.format(provider=prov)))
            fetched += 1
        except (urllib.error.URLError, TimeoutError) as exc:
            failed.append((prov, str(exc)))
    print(f"Fetched {fetched}/{len(api)} logos into {LOGO_DIR.relative_to(REPO_ROOT)}/")
    for prov, err in failed:
        print(f"  ! {prov}: {err}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
