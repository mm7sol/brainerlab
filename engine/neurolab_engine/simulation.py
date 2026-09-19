"""SIMULATION stage: seeded runner. Virtual manipulations touch the MODEL only."""
import random
from .models import get_model


def _apply_manipulations(edges, manipulations):
    manipulations = manipulations or {}
    removed = {(e.get("source"), e.get("target"), e.get("kind"))
               for e in manipulations.get("remove_edges", [])}
    edges = [e for e in edges
             if (e.get("source"), e.get("target"), e.get("kind")) not in removed]
    scales = manipulations.get("scale_weights", [])
    if scales:
        edges = [dict(e) for e in edges]
        for e in edges:
            for s in scales:
                f = s.get("edge_filter", {})
                if all(e.get(k) == v for k, v in f.items() if k in ("source", "target", "kind")):
                    w = e.get("weight")
                    e["weight"] = (1.0 if w is None else w) * s.get("factor", 1.0)
    return edges


def run_simulation(connectome, model_name, params, duration_ms, stimulus,
                   manipulations=None, seed=0):
    """Returns {spikes: {nid: [t...]}, meta}. Deterministic for fixed seed+noise=0."""
    manipulations = manipulations or {}
    model = get_model(model_name, params)
    rng = random.Random(seed)
    edges = _apply_manipulations(connectome.edges, manipulations)
    silenced = set(manipulations.get("silence", []))
    forced = set(manipulations.get("force_spike", []) + manipulations.get("activate", []))
    stim = {}
    for s in (stimulus or []):
        stim.setdefault(s["neuron"], []).append(
            (s.get("t_start_ms", 0), s.get("t_end_ms", 0), s.get("amplitude", 1.0)))

    def ext_at(nid, t):
        return sum(a for (a0, a1, a) in stim.get(nid, []) if a0 <= t < a1)

    state = {nid: {} for nid in connectome.nodes}
    spikes = {nid: [] for nid in connectome.nodes}
    incoming = {nid: 0.0 for nid in connectome.nodes}
    # pre-group persistent drive for propagation models: weight-null edges count as 1.0
    adj = {}
    for e in edges:
        if e.get("kind") == "electrical":
            continue  # V1: directed chemical drive only; gap junctions reported, not simulated
        w = e.get("weight")
        adj.setdefault(e["source"], []).append((e["target"], 1.0 if w is None else float(w)))

    for t in range(int(duration_ms)):
        fired = set()
        for nid in connectome.nodes:
            if nid in silenced:
                continue
            sp = model.step(state[nid], t, ext_at(nid, t), incoming[nid], rng)
            if nid in forced and model.name != "propagation":
                # virtual activation: clamp-drive above threshold each step
                state[nid]["V"] = model.params.get("v_rest", -65.0)
                sp = True
            if sp:
                fired.add(nid)
                spikes[nid].append(t)
        incoming = {nid: 0.0 for nid in connectome.nodes}
        for src in fired:
            for tgt, w in adj.get(src, []):
                if tgt in incoming:
                    incoming[tgt] += w
    return {"spikes": spikes,
            "meta": {"model": model_name, "model_version": model.version,
                     "duration_ms": int(duration_ms), "seed": seed,
                     "n_edges_used": len(edges),
                     "electrical_edges_excluded": sum(1 for e in connectome.edges
                                                      if e.get("kind") == "electrical")}}
