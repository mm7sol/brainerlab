# Contributing to BrainerLab

## Principles (non-negotiable)

1. **Never present a simulation as biological proof.** Label every claim:
   `FACT` (observed data + source), `SIMULATION RESULT` (computed from a run),
   `HYPOTHESIS`, `INTERPRETATION`.
2. **Never invent data.** Missing data → explicit gap + stub/ingester, never fabricated numbers.
3. **Never redistribute data beyond its licence.** Metadata + links + transformations only,
   unless the licence clearly allows it. Cite the paper for every dataset.
4. **Reproducibility first:** every experiment carries dataset version, model version,
   parameters, seed, engine version. Deterministic re-runs are tested.

## Workflow

- Pick a milestone (`docs/architecture.md`), open an issue, small PRs.
- Add/extend tests in `tests/test_all.py` (stdlib unittest, must pass offline).
- New species: add registry entry in `data/registry/datasets.json` + `scripts/ingest_<name>.py`.
  Do not touch the engine API.
- New model: subclass `engine/neurolab_engine/models.py::BaseModel`, document every parameter
  (units, default, source or "modelling choice"), bump `ENGINE_VERSION` if semantics change.

## Checks before PR

```powershell
python tests/test_all.py
python scripts/make_reference_circuit.py --check
```
