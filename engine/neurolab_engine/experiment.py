"""EXPERIMENT stage: IDs (NL-EXP-######), validation, export dicts."""
import datetime

REQUIRED = ["species", "dataset_id", "model", "duration_ms"]


def new_experiment_id(counter):
    return f"NL-EXP-{counter:06d}"


def validate_experiment(payload, dataset, models):
    errors = []
    for k in REQUIRED:
        if k not in payload:
            errors.append(f"missing field: {k}")
    if payload.get("model") not in models:
        errors.append(f"unknown model: {payload.get('model')}")
    try:
        model_cls = models[payload["model"]]
        unknown = sorted(set((payload.get("parameters") or {})) - set(model_cls.defaults))
        if unknown:
            errors.append(f"unknown parameters for {payload['model']}: {unknown}")
    except KeyError:
        pass
    node_ids = {n["id"] for n in dataset.get("nodes", [])}
    for s in payload.get("stimulus", []):
        if s.get("neuron") not in node_ids:
            errors.append(f"unknown stimulus neuron: {s.get('neuron')}")
    man = payload.get("manipulations", {}) or {}
    for nid in list(man.get("silence", [])) + list(man.get("activate", [])) + list(man.get("force_spike", [])):
        if nid not in node_ids:
            errors.append(f"unknown manipulated neuron: {nid}")
    for e in man.get("remove_edges", []):
        if e.get("source") not in node_ids or e.get("target") not in node_ids:
            errors.append(f"unknown edge endpoints: {e}")
    if not isinstance(payload.get("duration_ms", 0), int) or payload["duration_ms"] <= 0:
        errors.append("duration_ms must be a positive integer")
    if errors:
        raise ValueError("; ".join(errors))


def experiment_to_dict(exp_id, payload, dataset_meta, engine_version, model_version):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {"experiment_id": exp_id, "kind": "computational simulation (not biological evidence)",
            "research_question": payload.get("research_question"),
            "species": payload["species"], "dataset_id": payload["dataset_id"],
            "dataset_version": dataset_meta.get("version"),
            "model": payload["model"], "model_version": model_version,
            "parameters": payload.get("parameters", {}),
            "stimulus": payload.get("stimulus", []),
            "manipulations_virtual_only": payload.get("manipulations", {}),
            "duration_ms": payload["duration_ms"], "seed": payload.get("seed", 0),
            "engine_version": engine_version, "created_utc": now,
            "dataset_provenance": {k: dataset_meta.get(k) for k in
                                   ("source", "publication", "license", "citation",
                                    "completeness", "limitations")}}
