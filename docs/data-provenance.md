# Data provenance

Every number in this repository must answer: *where did you come from?*
Provenance is tracked at three levels: the **registry**, the **dataset
file**, and the **experiment record**.

## 1. Registry — `data/registry/datasets.json`

Single source of truth for dataset metadata. Each entry carries:

| Field | Meaning |
|---|---|
| `id` / `name` / `species` / `version` | Stable identity + version |
| `source` | Origin (lab, archive, or `BrainerLab` for own illustrative subsets, or `user upload`) |
| `publication` / `citation` | Citable paper or consensus reference |
| `license` | Governing licence — **code licence (MIT) never covers datasets** |
| `download_url` | Where to obtain the original source (`null` for own files) |
| `neurons` / `synapses` | Human-readable scope with qualifications |
| `completeness` / `limitations` | What is covered — and what is NOT |
| `status` | `bundled` \| `download_on_demand` \| `metadata_only` \| `imported` |
| `type` | `observed biological data` vs `illustrative model subset` vs `planned` vs `user-provided circuit (unverified biology)` |

Machine schema: `data/schemas/dataset.schema.json` (files) and
`data/schemas/provenance.schema.json` (experiment-embedded block).

## 2. Dataset files — `data/processed/`

| File | Source | Licence | Status |
|---|---|---|---|
| `c_elegans_reference_circuit_v1.json` | BrainerLab, built by `scripts/make_reference_circuit.py` from textbook consensus (Chalfie et al. 1985; Wicks & Rankin 1995) | MIT (own file; topology = cited consensus, no copied bulk data) | **Bundled.** 16-neuron illustrative subset, unweighted (`weight: null`), schematic display-only coordinates. NOT a connectome. |
| `c_elegans_varshney2011_v1.json` | Varshney et al. 2011 (PLOS Comput. Biol., CC-BY) via OpenWorm ConnectomeToolbox (MIT); built by `scripts/ingest_varshney.py` | CC-BY paper + MIT accessor; redistribution with attribution | **Bundled with citation** (281 nodes incl. BWM aggregator; 2194 directed chemical pairs + gap entries). Rebuild anytime via the ingest script. |
| `drosophila_courtship_subset_v1.json` | BrainerLab, built by `scripts/make_courtship_subset.py` from review consensus (Clowney 2015; Kallman 2015; Pavlou & Goodwin 2013) | MIT (own file) | **Bundled.** 9-cell-type illustrative subset, qualitative E/I edges. NOT measured connectivity. |
| `data/raw/NeuronConnect.xls` | OpenWorm ConnectomeToolbox (source for the Varshney ingest) | Per-source terms | **Never committed** (`data/raw/*` is gitignored). Downloaded on demand by `scripts/ingest_varshney.py`. |

Datasets that may **not** be redistributed are never bundled — only metadata,
links and loader stubs are kept:

- **FlyWire FAFB v783** (CC BY-NC 4.0): registry entry + citation + portal
  link; loader stub planned. No bulk data in this repo.
- **Cook et al. 2019** (Nature source-data terms): registry entry; bulk
  download via wormwiring.org only (`scripts/ingest_cook.py` instructs).
- **Zebrafish / mouse**: registry stubs; region/circuit level only for mouse,
  no whole-brain claims.

## 3. Experiment records — `experiments/`

Every record embeds a `dataset_provenance` block (`source`, `publication`,
`license`, `citation`, `completeness`, `limitations`) plus `dataset_version`,
`model`, `model_version`, `parameters`, `seed` and `engine_version` (schema:
`experiments/schema.json`). The chain is served by
`GET /api/provenance/{experiment_id}`:

```
Dataset → Version → Source → Publication → Transformation → Simulation → Result
```

Exports carry provenance too: `.csv` files start with a `#` header line
(experiment, dataset + version, model + version, seed, engine,
`COMPUTATIONAL SIMULATION`).

## Redistribution rule

> Do NOT redistribute a dataset unless its licence permits it. If in doubt,
> ship metadata + obtain-instructions instead of bytes.

Concretely: reference/courtship subsets (own MIT files) and the
Varshney-derived JSON (CC-BY with registry citation) are bundled; everything
else is `download_on_demand` or `metadata_only`. Final licence choice for the
project remains subject to legal review (see `LICENSE`).
