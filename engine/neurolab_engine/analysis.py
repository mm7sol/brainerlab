"""ANALYSIS + BEHAVIOR stages (model readouts only — never animal behaviour)."""

FORWARD_SET = {"AVBL", "AVBR", "PVCL", "PVCR", "DB1", "VB1"}
BACKWARD_SET = {"AVAL", "AVAR", "AVDL", "AVDR", "DA1"}


def summarise(spikes, duration_ms):
    dur_s = max(duration_ms / 1000.0, 1e-9)
    per = {n: {"count": len(ts), "rate_hz": round(len(ts) / dur_s, 3)} for n, ts in spikes.items()}
    total = sum(len(ts) for ts in spikes.values())
    fwd = sum(len(spikes.get(n, [])) for n in FORWARD_SET if n in spikes)
    bwd = sum(len(spikes.get(n, [])) for n in BACKWARD_SET if n in spikes)
    denom = max(fwd + bwd, 1)
    return {"per_neuron": per, "total_spikes": total,
            "mean_rate_hz": round(total / max(len(spikes), 1) / dur_s, 3),
            "behavior_proxy": {
                "forward_bias": round((fwd - bwd) / denom, 4),
                "note": "MODEL proxy from command/motor neuron spikes, not animal behaviour."}}


def compare(sum_normal, sum_modified):
    rows, d_total = [], sum_modified["total_spikes"] - sum_normal["total_spikes"]
    for n in sum_normal["per_neuron"]:
        a = sum_normal["per_neuron"][n]["count"]
        b = sum_modified["per_neuron"].get(n, {}).get("count", 0)
        rows.append({"neuron": n, "normal": a, "modified": b, "delta": b - a,
                     "pct": round(100.0 * (b - a) / a, 1) if a else (None if b == 0 else 100.0)})
    rows.sort(key=lambda r: (abs(r["delta"]), r["neuron"]), reverse=True)
    base = sum_normal["total_spikes"]
    return {"delta_total": d_total,
            "pct_total": round(100.0 * d_total / base, 2) if base else (0.0 if d_total == 0 else 100.0),
            "per_neuron": rows,
            "behavior_delta": round(sum_modified["behavior_proxy"]["forward_bias"]
                                    - sum_normal["behavior_proxy"]["forward_bias"], 4)}
