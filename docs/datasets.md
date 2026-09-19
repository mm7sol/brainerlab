# Datasets — analysis, licences, decisions (2026-09-18)

## C. elegans (priority 1) ✅ exploitable

| Source | Content | Licence / terms | Technical path | Decision |
|---|---|---|---|---|
| White et al. 1986 (Phil. Trans. R. Soc.) | original EM reconstructions | classic paper, figures/tables citable; no bulk machine file | via derivatives | cite as origin |
| Varshney et al. 2011, PLoS Comput. Biol. e1001066 | corrected wiring (herm., excl. pharynx): **chemical 281×281, 2309 pairs, Σ7804 synapses; electrical 1031 entries / 517 pairs, Σ1777** | **CC-BY** (PLOS) + data freely shared via WormAtlas; `lrvarshney/elegans` .mat files | `scripts/ingest_varshney.py` (downloads `NeuronConnect.xls` from OpenWorm ConnectomeToolbox, MIT repo) | **first production dataset** |
| Cook et al. 2019, Nature (herm. + male whole-animal) | full connectomes incl. muscles | Nature paper + source data (data-availability statement); wormwiring.org | `scripts/ingest_cook.py` stub → instruct download from wormwiring | second C. elegans dataset (M1 stretch) |
| OpenWorm ConnectomeToolbox (+ `cect` python pkg) | curated matrices for all above | **MIT** (code/repo) | optional `pip install` path documented | supported accessor |
| Bundled `c_elegans_reference_circuit_v1.json` | 14-neuron touch-withdrawal **illustrative subset**, unweighted | own file, MIT (topology = textbook consensus: Chalfie mechanosensory circuit; Wicks & Rankin) | built by `scripts/make_reference_circuit.py` | demo + deterministic tests only, labelled as such |

Neuron counts shown in UI always carry their dataset scope, e.g. "281 nodes in Varshney-2011 matrix
(pharynx excluded)" — never "the worm has exactly N neurons" without qualification.

## Drosophila (priority 2) ⏳ metadata only

FlyWire public releases (FAFB v783, Oct 2023 snapshot; Codex) are **CC BY-NC 4.0**.
Terms require citation + non-commercial use; pre-release cells need contributor agreement.
**Decision:** no bulk bundling. Registry holds metadata + links + citation; loader stub planned (M7).
Adult whole-brain ≈ 130k+ neurons — UI/API already paginated and subgraph-only.

## Zebrafish (M8) ⏳ / Mouse (M9) ⏳

Registry stubs with honest status (`no_bundled_data`, scope notes: zebrafish larva circuits;
mouse = region/circuit level only, **no whole-brain simulation claims**). Ingesters later.

## Common data schema (all species)

```json
{"id":"...","species":"...","version":"...","source":"...","publication":"...",
 "license":"...","citation":"...","download_url":"...","neurons":"...","synapses":"...",
 "completeness":"...","limitations":"...","status":"bundled|download_on_demand|metadata_only",
 "nodes":[{"id":"AVAL","class":"AVA","type":"interneuron","region":"head",...}],
 "edges":[{"source":"ALML","target":"AVAL","kind":"chemical","weight":null,...}]}
```

`weight:null` = unknown/unquantified (never silently 1). Coordinates in reference file are
**schematic layout for display only** (`x,y` + `position_note`), not measured anatomy.
