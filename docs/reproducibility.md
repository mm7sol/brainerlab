# Reproducibility

Experiment ID: `NL-EXP-######` (sequential, file-backed counter `experiments/_counter.json`
locally; shared atomic counter in production when KV is configured).
Stored file `experiments/NL-EXP-######.json` contains: species, dataset (+version),
model (+version), parameters, stimulus, manipulations, duration, seed, engine version,
timestamps, results (both arms), analysis, provenance block, references.
Full field schema: `experiments/schema.json`. Minimal runnable payload example:
`experiments/examples/minimal-lif.json`.

- Determinism: same dataset + same model + same parameters + same seed ⇒
  byte-identical spike trains (reference: seed 42, engine 0.1.0, model lif v1,
  default `noise=0.0`; asserted in `tests/test_all.py`, golden values
  normal=48 / modified=40). Non-default `noise` still uses the seeded RNG
  stream, so re-runs with the same seed reproduce; what is NOT reproduced
  across engine versions is behaviour after a semantic change — hence
  `ENGINE_VERSION` bumps and the freshness check on the reference experiment.
- Scope notes: V1 simulates directed chemical drive only; electrical
  (gap-junction) edges are reported in data but excluded from dynamics and
  counted in `meta.electrical_edges_excluded`. Unweighted (`null`) edges count
  as unit weight *inside the model step* (documented in `docs/models.md`).
- Export: `GET /api/export/{id}.json` (full file), `.csv` (per-neuron counts normal vs
  modified + provenance header lines starting with `#`).
- Report (`GET /api/reports/{id}`): question, dataset, model, params, manipulations,
  results, stats, limitations, reproducibility block, publications — header states
  "computational simulation, not biological evidence".
- Provenance endpoint returns the ordered chain dataset → … → result for UI display.
