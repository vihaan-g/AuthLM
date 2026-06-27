# scripts/

Operational scripts for AuthLM.

## `refresh_models_dev.py`

Re-vendors the offline models.dev snapshot from the live source.

```bash
python3 scripts/refresh_models_dev.py
```

- Fetches `https://models.dev/api.json` and `https://models.dev/models.json`.
- Writes the merged result to `src/authlm/_vendor/models-dev-snapshot.json`.
- Best-effort fetches each provider's SVG logo to `src/authlm/_vendor/_logos/`.
- If the network is unavailable, the existing vendored snapshot is **left unchanged** and the script exits non-zero. The CI pipeline should treat a non-zero exit as a soft failure, not a build break — the offline fallback is intentionally load-bearing.

The vendored snapshot's `_meta.hand_crafted: true` flag flips to `false` (and `_meta.fetched_at` is updated) on a successful run.
