# scripts/

Operational scripts for AuthLM.

## `refresh_models_dev.py`

Re-vendors the offline models.dev snapshot from the live source.

```bash
python3 scripts/refresh_models_dev.py
```

- Fetches `https://models.dev/api.json`.
- Writes the result to `src/authlm/_vendor/models-dev-snapshot.json` in the flat `{provider_id: metadata}` shape that `authlm.models_dev` expects.
- If the network is unavailable, the existing vendored snapshot is **left unchanged** and the script exits non-zero. The CI pipeline should treat a non-zero exit as a soft failure, not a build break — the offline fallback is intentionally load-bearing.

**v0.1.0 status: SCAFFOLDING.** The `authlm.models_dev` module is implemented and tested but not wired into providers. Providers hardcode their metadata for v0.1.0. This script is ready for v0.2 when the join against models.dev's api.json is wired in.
