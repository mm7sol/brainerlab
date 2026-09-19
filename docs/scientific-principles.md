# Scientific principles

> **BrainerLab is currently under development. It is not publicly live yet.**
> Nothing in this repository is biological proof. Everything the platform
> computes is labelled for what it is.

## The epistemic rule

```
Observed data
≠
Computational model
≠
Simulation
≠
AI interpretation
```

These four levels are strictly separated in code, in data and in the UI:

| Level | What it is | Where it lives | How it is labelled |
|---|---|---|---|
| **Observed data** | Measurements from documented sources (e.g. EM wiring diagrams compiled in cited papers) | `data/registry/datasets.json`, `data/processed/`, `data/raw/` (local only) | `FACT` + source citation; registry `type` says `observed biological data` |
| **Computational model** | A representation of data with explicit modelling choices (e.g. `lif` v1: thresholds, time constants — see `docs/models.md`) | `engine/neurolab_engine/models.py` | Parameters documented as `modelling choice` unless a `source` says otherwise |
| **Simulation** | Output of running a model on a circuit (`spikes`, summaries, normal-vs-modified comparison) | `experiments/NL-EXP-*.json` → `results`; `GET /api/results/{id}` | `SIMULATION RESULT` + seed/engine/model versions; reports carry the header `COMPUTATIONAL SIMULATION — not biological evidence` |
| **AI interpretation** | Rule-based textual reading of platform data (`POST /api/ai/explain`) | Response `answer` + `caution` fields | Every sentence prefixed `FACT` / `SIMULATION RESULT` / `HYPOTHESIS` / `INTERPRETATION`; response ends with `AI interpretation — verify against data and cited publications` |

## Consequences

1. **Simulation results are not biological proof.** A run shows what a model
   does on a circuit — never what the animal does. The `behavior_proxy`
   (`forward_bias`) is a toy readout over model spikes, explicitly noted as
   `MODEL proxy from command/motor neuron spikes, not animal behaviour.`
2. **Virtual manipulations touch the model only.** `silence`, `activate`,
   `force_spike`, `scale_weights`, `remove_edges` are stored under
   `manipulations_virtual_only` and labelled **Virtual manipulation** in the
   UI and reports.
3. **AI-generated text is hypothesis, not fact.** The assistant reasons only
   over platform data, refuses causal biological claims unless a registry
   publication supports them, and labels every sentence (see
   `backend/app/main.py::ai_explain`).
4. **Missing data is an explicit gap, never an invention.** Unintegrated
   datasets are registry stubs (`metadata_only`) with a loader slot — e.g.
   FlyWire (CC BY-NC 4.0, no bulk bundling), zebrafish, mouse. Unknown edge
   strengths are `weight: null`, never silently `1` (the engine documents
   where unit weight is assumed *inside the model step*).
5. **No claim without a source.** Neuron counts always carry dataset scope
   (e.g. `281 nodes in Varshney-2011 matrix (pharynx excluded)`), never
   `the worm has exactly N neurons` unqualified. Mouse work is region/circuit
   level only — whole-brain simulation claims are out of scope and rejected
   in tests (`test_no_whole_brain_mouse_claim`).

## For contributors

See `CONTRIBUTING.md`: label every claim, never invent data, never
redistribute data beyond its licence, and keep every experiment reproducible
(dataset + model + parameters + seed + engine version).
