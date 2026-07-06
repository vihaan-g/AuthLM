from __future__ import annotations

import os
from pathlib import Path

from authlm.stores import get_user_data_path


def get_metadata_path(override: Path | None) -> Path:
    """Resolve metadata path: explicit override > env var > default."""
    if override is not None:
        return override
    env = os.environ.get("AUTHLM_METADATA_PATH")
    if env is not None:
        return Path(env)
    env_user_path = os.environ.get("AUTHLM_USER_PATH")
    if env_user_path is not None:
        return Path(env_user_path) / "metadata.json"
    return get_user_data_path() / "metadata.json"
