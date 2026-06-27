#!/usr/bin/env python3
"""Refresh the vendored models.dev snapshot.

Fetches the combined provider+model catalog from https://models.dev
and writes it into the local vendored copy at
``src/authlm/_vendor/models-dev-snapshot.json``.

If the network is unavailable, the existing vendored snapshot is left
unchanged and a non-zero exit code is returned.  The CI pipeline should
treat a non-zero exit from this script as a soft failure, not a build
break — the offline fallback is intentionally load-bearing.

v0.1.0 status: SCAFFOLDING. The `authlm.models_dev` module is implemented
and tested but not wired into providers. Providers hardcode their
metadata for v0.1.0. This script is ready for v0.2 when the join against
models.dev's api.json is wired in. The script writes the flat
``{provider_id: metadata}`` shape that models_dev.py expects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "src" / "authlm" / "_vendor" / "models-dev-snapshot.json"

API_URL = "https://models.dev/api.json"

TIMEOUT = 15.0  # seconds


def main() -> int:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            response = client.get(API_URL)
            response.raise_for_status()
            api = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            print(f"ERROR: network refresh failed: {exc!r}", file=sys.stderr)
            print("Leaving existing snapshot untouched.", file=sys.stderr)
            return 1

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(api, indent=2) + "\n")
    print(f"Updated {SNAPSHOT_PATH.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
