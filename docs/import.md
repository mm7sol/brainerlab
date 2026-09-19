# User dataset imports

Visitors who own a circuit file can import it: Datasets tab →
**IMPORT YOUR OWN CIRCUIT**, or `POST /api/datasets/import` directly.
Two formats: `{nodes, edges}` JSON, or a `csv` edge-list string
(`source,target[,kind,weight]`, header auto-detected, comma/semicolon/tab —
handy for lists downloaded elsewhere, e.g. wormwiring edge lists you fetched
yourself under their terms).

## Format

```json
{"nodes": [{"id": "A", "type": "sensory"}],
 "edges": [{"source": "A", "target": "B", "kind": "chemical"}]}
```

- Node: required string `id`; optional `type` (`sensory`|`interneuron`|`motor`),
  `class`/`region`/`function` (short text), numeric `x`/`y`.
- Edge: `source` + `target` must reference existing nodes;
  `kind` is `chemical` (default) or `electrical`; optional numeric `weight`.
- Caps: ≤10 000 nodes, ≤100 000 edges, ≤4 MB body (whole brains welcome
  at circuit scale). Ids are uppercased on import so search, stimulus and
  manipulations match engine conventions.
- Simulations are capped at 750 000 neuron-steps (duration × nodes, both
  arms): shorten `duration_ms` for very large circuits (`413` otherwise).

## Guarantees

- Strict validation (`422` with the reason otherwise); engine-compatibility
  check via `Connectome` construction.
- `researcher` role required (`403` for visitors); `DELETE
  /api/datasets/import/{id}` removes it (registry datasets are protected).
- Labelled `imported` / UNVERIFIED everywhere: provenance states user upload,
  never mixed with curated data.
- Stored in shared KV when configured (chunked `nl:ds:*` values + `nl:ds:meta`
  hash, so listings never fetch full documents), else on disk
  (`data/imports/`, gitignored) or `/tmp` on serverless.
- Immediately usable in Explorer, Lab, experiments and simulations.

## Tests

`tests/test_import.py`: id normalization, all rejection cases, full
import → explore → simulate → delete flow, auth guards.
