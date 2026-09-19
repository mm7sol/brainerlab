# BRAINERLAB

> An open laboratory for exploring and experimenting with neural circuits.

> **BrainerLab is currently under development. It is not publicly live yet.**

BrainerLab is a browser-based laboratory for neural circuit exploration.
It lets you browse connectome datasets, run **virtual experiments**
(simulations of computational models — never experiments on animals),
visualise circuits in 2D (and 3D via lazy-loaded three.js), and share
reproducible experiment records with JSON/CSV export and full provenance.

*C. elegans* is the initial reference system. Other organisms (fly,
zebrafish, mouse circuits) are prepared as registry entries with the same
architecture, and integrated progressively as licences and loaders allow.

## Scientific principles

This repository strictly separates:

```
Observed data
≠
Computational model
≠
Simulation
≠
AI interpretation
```

- **Observed biological data** comes from documented sources (see
  `data/registry/datasets.json` + `docs/data-provenance.md`).
- **Computational models** (`iaf`, `lif`, `propagation` — see
  `docs/models.md`) are representations of those data; parameters are
  modelling choices unless a source says otherwise.
- **Simulations** are outputs of models. Simulation results are **not
  biological proof** — every report carries the header
  `COMPUTATIONAL SIMULATION — not biological evidence`.
- **AI-generated interpretations** (`POST /api/ai/explain`, rule-based over
  platform data only) are labelled sentence by sentence as
  `FACT` / `SIMULATION RESULT` / `HYPOTHESIS` / `INTERPRETATION`.

Full statement: `docs/scientific-principles.md`. It applies to code, data,
docs and the UI.

## What exists today (and only that)

- Dataset registry with licences, provenance and completeness
  (`data/registry/datasets.json`; schemas in `data/schemas/`).
- *C. elegans* reference circuit: 16-neuron touch-withdrawal illustrative
  subset (textbook topology, unweighted, schematic coordinates — NOT a
  connectome) plus an ingest script for the full Varshney et al. 2011 matrix
  (CC-BY, download on demand); see `docs/c-elegans.md`.
- Simulation engine, stdlib only, versioned and seeded (`ENGINE_VERSION`
  `0.1.0`; models `iaf` / `lif` / `propagation` v1).
- FastAPI backend: species, datasets, neurons, connections, subgraph,
  experiments, simulations, results, reports, provenance, rule-based AI
  assistant, JSON/CSV export, per-experiment pages.
- Web frontend served by the backend (no build step): dataset/species
  browsing, connectome explorer (canvas 2D + optional 3D, search, subgraph,
  inspector), Experiment Lab (virtual manipulations, normal vs modified
  arms, raster plots, comparison metrics), provenance view, university
  campus directory (auxiliary community feature).
- Reproducibility: sequential `NL-EXP-######` ids, full experiment schema
  (`experiments/schema.json`), reference experiment `NL-EXP-000001`
  (seed 42 → normal 48 / modified 40 spikes, asserted in tests).
- User circuit imports (JSON or CSV edge-list), strictly validated and
  always labelled **unverified** — never mixed with curated data.
- Tests: `tests/test_all.py` (stdlib unittest, offline, 26 tests green).

What is **not** here: no live deployment, no whole-brain claims (mouse is
region/circuit level only), no bundled FlyWire bulk data (CC BY-NC 4.0 —
metadata + links only), no external-LLM features.

## Repository layout

The layout follows the existing codebase (no duplicate or empty folders):

```
BrainerLab/
  README.md  LICENSE  CONTRIBUTING.md  CITATION.cff  SECURITY.md
  docs/                 scientific-principles, data-provenance, c-elegans,
                        architecture, datasets, models, api, reproducibility,
                        import, campus, 3d, DECISIONS
  data/registry/        datasets.json — metadata only (licences, links, versions)
  data/schemas/         dataset + provenance JSON schemas
  data/processed/       bundled circuit files (reference subset, Varshney matrix,
                        courtship subset) — cf. "circuits" in the outline
  data/raw/             gitignored — source files land here via scripts/ingest_*.py
  engine/neurolab_engine/  connectome, models, simulation, analysis, experiment
                        (stdlib only — cf. "engines" in the outline)
  backend/app/          FastAPI + zero-build web UI in backend/app/static/
                        (explorer + lab + visualisation — cf. "visualization")
  experiments/          schema.json, examples/, NL-EXP-000001.json (reference);
                        other runs are local-only runtime state
  scripts/              reference-circuit builder + dataset ingesters
  tests/                test_all.py (stdlib unittest, offline)
  frontend/             stub for the staged Next.js migration (see docs/architecture.md)
```

Adding a species = one registry entry + one ingester. The engine never changes.

## Quickstart (Windows PowerShell)

```powershell
git clone https://github.com/mm7sol/brainerlab ; cd brainerlab
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python scripts/make_reference_circuit.py      # (re)builds bundled reference file
python tests/test_all.py                      # 26 tests, offline
uvicorn backend.app.main:app --reload --port 8000
# open http://127.0.0.1:8000
```

Full Varshney et al. 2011 matrix (optional, download on demand):

```powershell
pip install xlrd
python scripts/ingest_varshney.py   # -> data/raw/ + data/processed/c_elegans_varshney2011_v1.json
```

Docker: `docker compose up --build` (API on :8000).

Environment: copy `.env.example` to `.env.local` and fill it in — **never
commit real tokens** (`.env*` is gitignored, only `.env.example` is
tracked). All variables are optional; without them the app uses local JSON
files. See `SECURITY.md` for what must never be committed.

## Reproduce the reference experiment

```
POST /api/simulations  { "experiment_id": "NL-EXP-000001" }
GET  /api/results/NL-EXP-000001
```

Deterministic: same dataset + same model + same parameters + same seed
(seed `42`, engine `0.1.0`, model `lif` v1) ⇒ byte-identical spike trains
(normal 48 / modified 40 spikes, asserted in tests). Minimal payload:
`experiments/examples/minimal-lif.json`. Record schema:
`experiments/schema.json`; details: `docs/reproducibility.md`.

## Species / datasets

| Species | Bundled now | Full data path |
|---|---|---|
| *C. elegans* (hermaphrodite) | Reference subset (16 neurons, textbook topology) + Varshney 2011 matrix (CC-BY, with citation) | `scripts/ingest_varshney.py`; Cook 2019 via wormwiring (metadata in registry) |
| *Drosophila* | Courtship-decision illustrative subset (9 cell types) + registry metadata (FlyWire FAFB v783 **CC BY-NC 4.0** — links only, no redistribution) | Loader stub planned |
| Zebrafish | Registry metadata only | Future ingester |
| Mouse | Registry metadata only, circuit level (no whole-brain claims) | Future ingester |

Per-source licences, completeness and limitations: `docs/data-provenance.md`
and `docs/datasets.md`. Code is MIT; **data keeps its own licence** (see
`LICENSE`).

## API (summary)

```
GET  /api/species  /api/datasets  /api/datasets/{id}
GET  /api/neurons?dataset_id=&q=&type=&region=&limit=&offset=
GET  /api/neurons/{id}?dataset_id=
GET  /api/connections?dataset_id=&source=&target=&kind=&limit=&offset=
GET  /api/graph/subgraph?dataset_id=&seeds=AVAL,AVAR&depth=1&direction=both&kind=all
GET  /api/experiments  POST /api/experiments
POST /api/simulations   GET /api/results/{id}  GET /api/reports/{id}
POST /api/ai/explain    GET /api/provenance/{experiment_id}
GET  /experiment/{id} (page)   GET /api/export/{id}.json|.csv
```

Interactive docs: `/docs` (Swagger), `/openapi.json`. Full contract: `docs/api.md`.

## Contributing / citation / licence

See `CONTRIBUTING.md`, `CITATION.cff`, `LICENSE` (MIT for code; **data
retains its own licence** — code licence never covers datasets) and
`SECURITY.md`. Legal review still required before any dataset redistribution.
