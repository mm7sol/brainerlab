# Architecture (concrete, V1)

## Pipeline (independent stages)

```
DATASET (registry + raw/processed files, versioned)
  → CONNECTOME (directed multigraph: neurons, edges w/ kind+weight?, spatial optional)
  → MODEL (plugin: iaf | lif | propagation, versioned params)
  → SIMULATION (seeded runner, dt=1ms, stimulus, virtual manipulations)
  → BEHAVIOR (model readouts only, e.g.toy forward/backward bias — labelled as such)
  → ANALYSIS (spike counts/rates, deltas normal vs modified, raster data)
```

Each stage has its own module and JSON schema; stages communicate via plain dicts/JSON so any
stage (file DB → Postgres, models, frontend) can be swapped.

## Components

- `engine/neurolab_engine/` — pure Python, **stdlib only**, no web/DB imports:
  `connectome.py` (load/query/subgraph/degrees), `models.py` (registry + 3 models),
  `simulation.py` (runner), `analysis.py` (metrics + comparison), `experiment.py`
  (ID minting `NL-EXP-######`, validation, export dict/CSV rows).
- `backend/app/main.py` — FastAPI; thin HTTP layer over the engine + registry.
  Persistence V1: JSON files (`experiments/`). Postgres + object storage later (M10);
  repository functions are isolated in `store_*()` helpers for that swap.
- `backend/app/static/` — V1 web UI (no build step, served by FastAPI): SPA tabs +
  canvas 2D explorer. Migration to Next.js/TypeScript + Three.js/WebGL (M2) keeps the
  same REST contract; see `docs/api.md`.
- `data/registry/datasets.json` — single source of truth for dataset metadata.
- `scripts/ingest_*.py` — download + normalise full datasets into `data/processed/`.

## Scale/performance strategy (M1→M10)

Pagination on every list endpoint; subgraph API with `depth/direction/kind` caps
(`MAX_SUBGRAPH_NODES=400`); frontend renders subgraphs only, canvas 2D now, WebGL +
LOD/clustering/streaming later; engine is O(steps × edges-in-subgraph) on the stimulated
subgraph, not the whole brain. Cache: registry + processed files in memory; HTTP ETags later.

## Roles (V1 stub → M10)

`visitor` (read), `researcher` (create experiments), `admin` (datasets). V1: role passed as
optional header, enforced on POST routes minimally; full auth later.
