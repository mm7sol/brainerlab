# DECISIONS (Architecture Decision Records — Milestone 1)

1. **First production dataset = Varshney et al. 2011** (PLOS CC-BY): corrected White-1986 wiring,
   machine-readable via OpenWorm ConnectomeToolbox (MIT). Bundled file is only an illustrative
   14-neuron subset; full matrix via `scripts/ingest_varshney.py` on demand. Rationale: only
   C. elegans source both licence-clean and technically tractable now.
2. **No FlyWire bulk data.** CC BY-NC 4.0 + contributor-agreement rules for pre-release cells ⇒
   metadata/links/stub only (M7). Same honesty pattern for zebrafish/mouse (M8/M9).
3. **Engine stdlib-only, framework-free.** Deterministic, testable offline, embeddable in any
   backend. NumPy/NetworkX optional later, never required for V1 correctness.
4. **Backend FastAPI + file-store JSON; frontend zero-build static.** Maximises runnable-now value
   on any machine; Postgres/Next.js/Three.js are staged migrations with a frozen REST contract.
5. **Unweighted reference edges (`weight:null`).** Textbook topology without invented strengths;
   engine treats null as unit weight only inside the model and says so.
6. **Schematic 2D coordinates labelled as display-only.** No fake anatomy.
7. **AI assistant is rule-based over platform data in V1** (no external LLM): every sentence is
   prefixed FACT / SIMULATION RESULT / HYPOTHESIS / INTERPRETATION; causal biological claims refused
   unless a registry publication supports them.
8. **Licence: MIT for code; data keeps its own licence.** Legal review still required.
