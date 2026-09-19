# C. elegans — data layers

*C. elegans* (hermaphrodite) is the initial reference system. Future
organisms (fly, zebrafish, mouse circuits) follow the same layered pattern;
see `data/registry/datasets.json` for their stubs.

## The four layers (never mixed)

```
raw / source data
  ≠ processed data
  ≠ computational model
  ≠ simulation output
```

| Layer | Location | Example | Licence |
|---|---|---|---|
| **Raw / source** | `data/raw/` (local only, gitignored) | `NeuronConnect.xls` downloaded from OpenWorm ConnectomeToolbox by `scripts/ingest_varshney.py` | Per-source terms; never redistributed from here |
| **Processed** | `data/processed/` (bundled) | `c_elegans_reference_circuit_v1.json` (built by `scripts/make_reference_circuit.py`); `c_elegans_varshney2011_v1.json` (built by `scripts/ingest_varshney.py`) | Own subsets: MIT; Varshney-derived: CC-BY with citation |
| **Computational model** | `engine/neurolab_engine/models.py` | `lif` v1 (+ `iaf`, `propagation`); parameters in `docs/models.md` | MIT (code) |
| **Simulation output** | `experiments/NL-EXP-*.json` → `results` (only `NL-EXP-000001.json` tracked) | Reference run: seed 42, engine 0.1.0, `lif` v1 → normal 48 / modified 40 spikes | Generated; reproducible, not observed |

Rebuild any processed file from its script:

```powershell
python scripts/make_reference_circuit.py      # reference subset
python scripts/make_reference_circuit.py --check  # verify bundled file matches
pip install xlrd; python scripts/ingest_varshney.py  # full Varshney matrix
```

## Reference subset vs full matrix vs user uploads

- **Reference circuit** (`c_elegans_reference_circuit`, v1.0.0): 16 neurons /
  23 directed qualitative edges of the touch-withdrawal circuit (Chalfie et
  al. 1985; Wicks & Rankin 1995). Unweighted, schematic coordinates,
  labelled `ILLUSTRATIVE SUBSET ONLY … NOT a connectome`. Used for demos and
  deterministic tests.
- **Varshney 2011 matrix** (`c_elegans_varshney2011`, v2011.1): corrected
  White-1986 wiring excl. pharynx (280 neurons + BWM aggregator; 2194
  directed chemical pairs + gap entries + NMJ aggregation). Observed-data
  compilation; gap-junction weights are counts, not conductances; no dynamics.
- **User-uploaded circuits**: imported via `POST /api/datasets/import`
  (JSON or CSV edge-list; strict validation, 422 on error). Stored separately
  (`data/imports/`, gitignored, or shared KV in production) and labelled
  **`imported` / UNVERIFIED user upload** everywhere — in listings, in
  provenance (`source: user upload`), and in results. Never mixed with
  curated reference data; `DELETE /api/datasets/import/{id}` removes them
  (registry datasets are protected).

See `docs/import.md` for the import format and `docs/datasets.md` for the
full per-source analysis.
