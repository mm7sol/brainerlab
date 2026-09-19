"""BrainerLab backend (FastAPI). Thin HTTP layer over engine + dataset registry.

Scientific-safety: every result payload carries its provenance; simulation outputs
are labelled as computational, never biological.
"""
import csv
import io
import json
import os
import re
import secrets
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from engine.neurolab_engine import (
    Connectome, MODEL_REGISTRY, run_simulation, summarise, compare,
    new_experiment_id, validate_experiment, experiment_to_dict, ENGINE_VERSION,
)
from backend.app.campus import router as campus_router

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = json.loads((ROOT / "data" / "registry" / "datasets.json").read_text(encoding="utf-8"))
# Vercel: filesystem is read-only except /tmp. Experiments written at runtime
# go to /tmp, while the bundled reference experiment is read from the repo.
EXP_DIR_ROOT = ROOT / "experiments"
EXP_DIR_TMP = Path("/tmp/neurolab_experiments")
ON_VERCEL = os.environ.get("VERCEL") == "1"
EXP_DIR = EXP_DIR_TMP if ON_VERCEL else EXP_DIR_ROOT
STATIC = Path(__file__).resolve().parent / "static"
MAX_SUBGRAPH_NODES = 400

app = FastAPI(title="BrainerLab API", version="0.1.0",
              description="Reproducible computational experiments on connectomes. "
                          "Simulations are computational models, not biological evidence.")
app.include_router(campus_router)

_datasets: dict = {}
_connectomes: dict = {}


def load_datasets():
    _datasets.clear()
    _connectomes.clear()
    for path in sorted((ROOT / "data" / "processed").glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        _datasets[doc["id"]] = doc
        _connectomes[doc["id"]] = Connectome(doc)
    # user imports persisted on disk (local dev); on KV they resolve lazily
    if _kv() is None:
        for did in import_store_ids():
            if did not in _datasets:
                doc = import_store_get(did)
                if doc:
                    _remember_import(doc)


def registry_entry(dataset_id):
    for d in REGISTRY["datasets"]:
        if d["id"] == dataset_id:
            return d
    return None


def dataset_or_404(dataset_id):
    if dataset_id in _datasets:
        return _datasets[dataset_id]
    doc = import_store_get(dataset_id)
    if doc is not None:
        _remember_import(doc)
        return doc
    raise HTTPException(404, f"unknown dataset '{dataset_id}'. "
                             f"Available: {sorted(_datasets)}")


def get_connectome(dataset_id):
    con = _connectomes.get(dataset_id)
    if con is None:
        dataset_or_404(dataset_id)
        con = _connectomes.get(dataset_id)
    if con is None:
        raise HTTPException(404, f"unknown dataset '{dataset_id}'")
    return con


# ---------------------------------------------------------------- user dataset imports
# Visitors can upload their own circuit JSON (if they own it). Validated
# strictly, capped in size, ids uppercased for engine compatibility, and
# always labelled UNVERIFIED user upload — never mixed with curated data.
MAX_IMPORT_NODES = 10000
MAX_IMPORT_EDGES = 100000
MAX_IMPORT_BYTES = 4_000_000
# keep every KV request well under typical serverless/KV size limits
KV_CHUNK = 400_000
# simulation cost ~= duration_ms x n_nodes per arm (x2 arms); cap total work
# so a run stays inside the serverless time budget
MAX_SIM_STEPS = 750_000
IMPORT_DIR_ROOT = ROOT / "data" / "imports"
IMPORT_DIR_TMP = Path("/tmp/neurolab_imports")
IMPORT_DIR = IMPORT_DIR_TMP if ON_VERCEL else IMPORT_DIR_ROOT
NODE_TYPES = {"sensory", "interneuron", "motor"}
EDGE_KINDS = {"chemical", "electrical"}

_imported_ids: set = set()


def _str_cap(v, limit=500):
    s = str(v)
    if len(s) > limit:
        raise ValueError(f"text field too long (>{limit} chars)")
    return s


def validate_import_doc(nodes, edges):
    if not isinstance(nodes, list) or not (1 <= len(nodes) <= MAX_IMPORT_NODES):
        raise ValueError(f"nodes: list of 1..{MAX_IMPORT_NODES}")
    if not isinstance(edges, list) or not (0 <= len(edges) <= MAX_IMPORT_EDGES):
        raise ValueError(f"edges: list of 0..{MAX_IMPORT_EDGES}")
    clean_nodes, seen = [], set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            raise ValueError("each node needs a string id")
        nid = n["id"].strip().upper()
        if not (1 <= len(nid) <= 64) or nid in seen:
            raise ValueError(f"bad or duplicate node id: {n.get('id')!r}")
        seen.add(nid)
        node = {"id": nid}
        if n.get("type") is not None:
            if n["type"] not in NODE_TYPES:
                raise ValueError(f"node {nid}: type must be sensory|interneuron|motor")
            node["type"] = n["type"]
        for k in ("class", "region", "function"):
            if n.get(k) is not None:
                node[k] = _str_cap(n[k])
        for k in ("x", "y"):
            if n.get(k) is not None:
                if not isinstance(n[k], (int, float)):
                    raise ValueError(f"node {nid}: {k} must be a number")
                node[k] = n[k]
        clean_nodes.append(node)
    clean_edges = []
    for e in edges:
        if not isinstance(e, dict):
            raise ValueError("each edge must be an object")
        try:
            s, t = e["source"].strip().upper(), e["target"].strip().upper()
        except (KeyError, AttributeError):
            raise ValueError("each edge needs source + target strings")
        if s not in seen or t not in seen:
            raise ValueError(f"edge {s}->{t}: unknown endpoint")
        kind = e.get("kind", "chemical")
        if kind not in EDGE_KINDS:
            raise ValueError(f"edge {s}->{t}: kind must be chemical|electrical")
        edge = {"source": s, "target": t, "kind": kind}
        if e.get("weight") is not None:
            if not isinstance(e["weight"], (int, float)):
                raise ValueError(f"edge {s}->{t}: weight must be a number or null")
            edge["weight"] = e["weight"]
        clean_edges.append(edge)
    return clean_nodes, clean_edges


def _import_slug(name):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "dataset").strip().lower()).strip("-")
    return f"custom-{(slug or 'dataset')[:40]}-{secrets.token_hex(3)}"


def parse_edge_csv(text):
    """Edge-list CSV/TSV -> (nodes, edges) for validate_import_doc.

    Columns: source, target[, kind[, weight]] — header row auto-detected
    (contains 'source'), otherwise positional. Delimiter: tab > ';' > ','.
    Lines starting with '#' and blank lines are skipped. Node ids are
    uppercased; errors carry 1-based line numbers.
    """
    import csv as _csv
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty csv")
    if len(text) > MAX_IMPORT_BYTES:
        raise ValueError("csv too large (>4 MB)")
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        raise ValueError("empty csv")
    first = lines[0]
    delim = "\t" if "\t" in first else (";" if ";" in first else ",")
    rows = list(_csv.reader(lines, delimiter=delim))
    header = [c.strip().lower() for c in rows[0]]
    if "source" in header and "target" in header:
        col = {name: header.index(name) for name in
               ("source", "target", "kind", "weight") if name in header}
        data = rows[1:]
    else:
        col = {"source": 0, "target": 1}
        if len(rows[0]) > 2:
            col["kind"] = 2
        if len(rows[0]) > 3:
            col["weight"] = 3
        data = rows
    nodes, seen, edges = [], set(), []
    for i, r in enumerate(data, start=2 if data is not rows else 1):
        try:
            s, t = r[col["source"]].strip().upper(), r[col["target"]].strip().upper()
        except (IndexError, AttributeError):
            raise ValueError(f"line {i}: need source + target")
        if not s or not t:
            raise ValueError(f"line {i}: empty endpoint")
        kind = r[col["kind"]].strip().lower() if "kind" in col and len(r) > col["kind"] and r[col["kind"]].strip() else "chemical"
        e = {"source": s, "target": t, "kind": kind}
        if "weight" in col and len(r) > col["weight"] and r[col["weight"]].strip():
            try:
                e["weight"] = float(r[col["weight"]])
            except ValueError:
                raise ValueError(f"line {i}: weight must be a number")
        edges.append(e)
        for nid in (s, t):
            if nid not in seen:
                seen.add(nid)
                nodes.append({"id": nid})
    if not nodes:
        raise ValueError("no edges found")
    return nodes, edges


def import_store_put(doc, meta):
    kv = _kv()
    if kv:
        raw = json.dumps(doc)
        chunks = [raw[i:i + KV_CHUNK] for i in range(0, len(raw), KV_CHUNK)]
        manifest = {"chunked": True, "n": len(chunks), "meta": meta}
        cmds = [["SET", f"nl:ds:{doc['id']}", json.dumps(manifest)],
                ["HSET", "nl:ds:meta", doc["id"], json.dumps(meta)]]
        for i, ch in enumerate(chunks):
            cmds.append(["SET", f"nl:ds:{doc['id']}:c{i}", ch])
        for j in range(0, len(cmds), 8):
            kv.pipe(cmds[j:j + 8])
        return
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    (IMPORT_DIR / f"{doc['id']}.json").write_text(json.dumps(doc), encoding="utf-8")


def import_store_get(dataset_id):
    kv = _kv()
    if kv:
        try:
            res = kv.pipe([["GET", f"nl:ds:{dataset_id}"]])[0]
            if not res:
                return None
            man = json.loads(res)
            if isinstance(man, dict) and "nodes" in man:
                return man  # legacy direct doc
            parts = []
            for j in range(0, man["n"], 8):
                gets = [["GET", f"nl:ds:{dataset_id}:c{i}"]
                        for i in range(j, min(j + 8, man["n"]))]
                parts.extend(kv.pipe(gets))
            return json.loads("".join(parts))
        except Exception:
            return None
    for d in (IMPORT_DIR, IMPORT_DIR_ROOT):
        p = d / f"{dataset_id}.json"
        if p.exists():
            return _read_json_silent(p)
    return None


def import_store_metas():
    """Lightweight {id: meta} for listings — no full-doc fetch on KV."""
    kv = _kv()
    if kv:
        try:
            flat = kv.pipe([["HGETALL", "nl:ds:meta"]])[0] or []
            it = iter(flat)
            return {k: json.loads(v) for k, v in zip(it, it)}
        except Exception:
            return {}
    out = {}
    for did in import_store_ids():
        doc = _datasets.get(did) or import_store_get(did)
        if doc:
            out[did] = import_meta_entry(doc)
    return out


def import_store_ids():
    kv = _kv()
    if kv:
        try:
            flat = kv.pipe([["HGETALL", "nl:ds:meta"]])[0] or []
            return sorted(flat[::2])
        except Exception:
            return []
    seen = set()
    for d in (IMPORT_DIR, IMPORT_DIR_ROOT):
        try:
            for f in d.glob("*.json"):
                seen.add(f.stem)
        except Exception:
            continue
    return sorted(seen)


def import_store_delete(dataset_id):
    kv = _kv()
    if kv:
        man = None
        try:
            res = kv.pipe([["GET", f"nl:ds:{dataset_id}"]])[0]
            man = json.loads(res) if res else None
        except Exception:
            man = None
        cmds = [["DEL", f"nl:ds:{dataset_id}"], ["HDEL", "nl:ds:meta", dataset_id]]
        if isinstance(man, dict) and man.get("chunked"):
            for i in range(man.get("n", 0)):
                cmds.append(["DEL", f"nl:ds:{dataset_id}:c{i}"])
        kv.pipe(cmds)
        return
    for d in (IMPORT_DIR, IMPORT_DIR_ROOT):
        try:
            (d / f"{dataset_id}.json").unlink(missing_ok=True)
        except Exception:
            continue


def _remember_import(doc):
    _datasets[doc["id"]] = doc
    _connectomes[doc["id"]] = Connectome(doc)
    _imported_ids.add(doc["id"])


def import_meta_entry(doc):
    n, e = len(doc["nodes"]), len(doc["edges"])
    return {"id": doc["id"], "name": doc.get("name", doc["id"]),
            "species": doc.get("species", "custom"), "version": "1.0.0-import",
            "status": "imported", "type": "user-provided circuit (unverified biology)",
            "source": "user upload", "publication": None,
            "license": "user-provided (stays with the uploader, never redistributed)",
            "citation": None, "download_url": None,
            "neurons": f"{n} nodes (user import)", "synapses": f"{e} edges (user import)",
            "completeness": "UNVERIFIED user upload: topology as provided, no biological claim.",
            "limitations": "Not curated or validated against any publication; simulations are model-only.",
            "bundled_nodes": n, "bundled_edges": e}


def exp_path(exp_id):
    return EXP_DIR / f"{exp_id}.json"


def _read_json_silent(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_experiment(exp_id):
    exp_id = exp_id.upper()
    # 0. shared KV first (when configured — survives serverless restarts)
    hit = kv_exp_get(exp_id)
    if hit:
        return hit
    # 1. runtime dir (/tmp on Vercel, repo dir locally)
    p = exp_path(exp_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # 2. fallback: bundled reference in the repo (Vercel read-only FS)
    fallback = EXP_DIR_ROOT / f"{exp_id}.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))
    raise HTTPException(404, f"unknown experiment '{exp_id}'")


def list_experiment_files():
    seen: dict = {}
    # merge both dirs, runtime version wins
    for d in (EXP_DIR, EXP_DIR_ROOT):
        try:
            files = sorted(d.glob("NL-EXP-*.json"))
        except Exception:
            continue
        for f in files:
            seen.setdefault(f.name, f)
    return sorted(seen.values(), key=lambda p: p.name)


# ---------------------------------------------------------------- shared KV for experiments
# Same store as campus memberships: when KV is configured, experiments survive
# serverless restarts. Otherwise the file logic below applies unchanged.
def _kv():
    try:
        from backend.app import campus_store
        s = campus_store.get_store()
        return s if isinstance(s, campus_store.KvRestBackend) else None
    except Exception:
        return None


def kv_exp_get(exp_id):
    kv = _kv()
    if not kv:
        return None
    try:
        res = kv.pipe([["GET", f"nl:exp:{exp_id}"]])[0]
        return json.loads(res) if res else None
    except Exception:
        return None


def kv_exp_ids():
    kv = _kv()
    if not kv:
        return []
    try:
        return kv.pipe([["SMEMBERS", "nl:exp:ids"]])[0] or []
    except Exception:
        return []


def save_experiment(record):
    """Persist to shared KV when configured, else to the runtime dir."""
    kv = _kv()
    if kv:
        try:
            kv.pipe([["SET", f"nl:exp:{record['experiment_id']}", json.dumps(record)],
                     ["SADD", "nl:exp:ids", record["experiment_id"]]])
            return
        except Exception:
            raise HTTPException(503, "experiment store unavailable")
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    exp_path(record["experiment_id"]).write_text(json.dumps(record, indent=2),
                                                 encoding="utf-8")


def require_researcher(x_role: str | None):
    if (x_role or "researcher") not in ("researcher", "admin"):
        raise HTTPException(403, "role 'researcher' or 'admin' required to create experiments "
                                 "(visitors may explore public data)")


def simulate_experiment(record):
    ds = dataset_or_404(record["dataset_id"])
    con = _connectomes[record["dataset_id"]]
    man_none = {"silence": [], "activate": [], "force_spike": [],
                "scale_weights": [], "remove_edges": []}
    normal = run_simulation(con, record["model"], record.get("parameters", {}),
                            record["duration_ms"], record.get("stimulus", []),
                            man_none, record.get("seed", 0))
    modified = run_simulation(con, record["model"], record.get("parameters", {}),
                              record["duration_ms"], record.get("stimulus", []),
                              record.get("manipulations_virtual_only", man_none),
                              record.get("seed", 0))
    s_n, s_m = summarise(normal["spikes"], record["duration_ms"]), \
        summarise(modified["spikes"], record["duration_ms"])
    record["results"] = {"normal": {"spikes": normal["spikes"], "summary": s_n, "meta": normal["meta"]},
                         "modified": {"spikes": modified["spikes"], "summary": s_m,
                                      "meta": modified["meta"]},
                         "comparison": compare(s_n, s_m)}
    return record


def _reference_is_fresh(doc) -> bool:
    try:
        return doc.get("engine_version") == ENGINE_VERSION and \
            doc.get("results", {}).get("normal", {}).get("meta", {}).get("model_version") == \
            MODEL_REGISTRY["lif"].version
    except Exception:
        return False


def ensure_reference_experiment():
    try:
        EXP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    ref = EXP_DIR / "NL-EXP-000001.json"
    if ref.exists() and _reference_is_fresh(_read_json_silent(ref)):
        return
    # On Vercel (/tmp empty at cold start): reuse the bundled reference if fresh,
    # avoids an expensive rebuild and guarantees the demo experiment exists.
    bundled = EXP_DIR_ROOT / "NL-EXP-000001.json"
    if bundled.exists() and bundled.resolve() != ref.resolve() \
            and _reference_is_fresh(_read_json_silent(bundled)):
        try:
            shutil.copyfile(bundled, ref)
            if not (EXP_DIR / "_counter.json").exists():
                (EXP_DIR / "_counter.json").write_text(json.dumps({"counter": 1}),
                                                       encoding="utf-8")
            return
        except Exception:
            pass
    try:
        payload = {"species": "caenorhabditis_elegans", "dataset_id": "c_elegans_reference_circuit",
                   "model": "lif", "parameters": {}, "duration_ms": 200, "seed": 42,
                   "stimulus": [{"neuron": "PLML", "t_start_ms": 10, "t_end_ms": 60, "amplitude": 50.0},
                                {"neuron": "PLMR", "t_start_ms": 10, "t_end_ms": 60, "amplitude": 50.0}],
                   "manipulations": {"silence": ["PVCL"]},
                   "research_question": "Reference: how does virtual inhibition of PVCL alter "
                                        "posterior-touch propagation in the lif model?"}
        ds = dataset_or_404(payload["dataset_id"])
        validate_experiment(payload, ds, MODEL_REGISTRY)
        meta = next(d for d in REGISTRY["datasets"] if d["id"] == payload["dataset_id"])
        record = experiment_to_dict("NL-EXP-000001", payload, meta, ENGINE_VERSION,
                                    MODEL_REGISTRY[payload["model"]].version)
        record = simulate_experiment(record)
        ref.write_text(json.dumps(record, indent=2), encoding="utf-8")
        (EXP_DIR / "_counter.json").write_text(json.dumps({"counter": 1}), encoding="utf-8")
    except Exception:
        # Never crash import on serverless (read-only FS, cold start, ...).
        # Read endpoints still serve bundled data via EXP_DIR_ROOT fallback.
        pass


load_datasets()
ensure_reference_experiment()

# ---------------------------------------------------------------- species/datasets
@app.get("/api/health")
def health():
    return {"ok": True, "engine": ENGINE_VERSION, "vercel": ON_VERCEL}


@app.get("/api/species")
def get_species():
    return {"species": REGISTRY["species"]}


@app.get("/api/datasets")
def get_datasets(species: str | None = None):
    ds = REGISTRY["datasets"]
    if species:
        ds = [d for d in ds if d["species"] == species]
    out = []
    for d in ds:
        bundled = _datasets.get(d["id"])
        out.append({**d,
                    "bundled_nodes": len(bundled["nodes"]) if bundled else None,
                    "bundled_edges": len(bundled["edges"]) if bundled else None})
    for did, e in import_store_metas().items():
        if did not in _datasets:
            doc = import_store_get(did)
            if doc:
                _remember_import(doc)
                e = import_meta_entry(doc)
            else:
                continue
        if species and e.get("species") != species:
            continue
        out.append(e)
    return {"datasets": out, "registry_version": REGISTRY["registry_version"]}


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    meta = registry_entry(dataset_id)
    if meta:
        bundled = _datasets.get(dataset_id)
        return {**meta,
                "bundled_nodes": len(bundled["nodes"]) if bundled else None,
                "bundled_edges": len(bundled["edges"]) if bundled else None}
    doc = _datasets.get(dataset_id) or import_store_get(dataset_id)
    if doc:
        if dataset_id not in _datasets:
            _remember_import(doc)
        return import_meta_entry(doc)
    raise HTTPException(404, f"unknown dataset '{dataset_id}'")


@app.post("/api/datasets/import", status_code=201)
def import_dataset(body: dict, x_role: str | None = Header(None)):
    require_researcher(x_role)
    if len(json.dumps(body)) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "import too large (>4 MB)")
    name = str(body.get("name") or "Custom circuit")[:120]
    species = str(body.get("species") or "custom")[:64]
    try:
        if body.get("csv") is not None:
            nodes, edges = validate_import_doc(*parse_edge_csv(body.get("csv")))
        else:
            nodes, edges = validate_import_doc(body.get("nodes"), body.get("edges"))
    except ValueError as e:
        raise HTTPException(422, f"invalid dataset: {e}")
    uid = _import_slug(name)
    while uid in _datasets or import_store_get(uid):
        uid = _import_slug(name)
    doc = {"id": uid, "name": name, "species": species, "version": "1.0.0-import",
           "status": "imported", "type": "user-provided circuit (unverified biology)",
           "source": "user upload", "publication": None,
           "license": "user-provided (stays with the uploader, never redistributed)",
           "citation": None,
           "completeness": "UNVERIFIED user upload: topology as provided, no biological claim.",
           "limitations": "Not curated or validated against any publication; simulations are model-only.",
           "nodes": nodes, "edges": edges}
    try:
        Connectome(doc)
    except Exception as e:
        raise HTTPException(422, f"incompatible with engine: {e}")
    try:
        import_store_put(doc, import_meta_entry(doc))
    except Exception:
        raise HTTPException(503, "import store unavailable")
    _remember_import(doc)
    return {"id": uid, "name": name, "species": species,
            "nodes": len(nodes), "edges": len(edges)}


@app.delete("/api/datasets/import/{dataset_id}")
def delete_import(dataset_id: str, x_role: str | None = Header(None)):
    require_researcher(x_role)
    if dataset_id not in _imported_ids and import_store_get(dataset_id) is None:
        raise HTTPException(404, f"unknown imported dataset '{dataset_id}'")
    try:
        import_store_delete(dataset_id)
    except Exception:
        raise HTTPException(503, "import store unavailable")
    _datasets.pop(dataset_id, None)
    _connectomes.pop(dataset_id, None)
    _imported_ids.discard(dataset_id)
    return {"deleted": dataset_id}

# ---------------------------------------------------------------- neurons/graph
@app.get("/api/neurons")
def list_neurons(dataset_id: str, q: str | None = None, type: str | None = None,
                 region: str | None = None, limit: int = Query(50, le=500),
                 offset: int = 0):
    ds = dataset_or_404(dataset_id)
    nodes = ds["nodes"]
    if q:
        nodes = [n for n in nodes if q.upper() in n["id"].upper()]
    if type:
        nodes = [n for n in nodes if n.get("type") == type]
    if region:
        nodes = [n for n in nodes if n.get("region") == region]
    return {"total": len(nodes), "neurons": nodes[offset:offset + limit]}


@app.get("/api/neurons/{neuron_id}")
def get_neuron(neuron_id: str, dataset_id: str):
    con = get_connectome(dataset_id)
    node = con.get(neuron_id.upper())
    if not node:
        raise HTTPException(404, f"unknown neuron '{neuron_id}' in '{dataset_id}'")
    return {"neuron": node,
            "degree": {"chemical": con.degree(node["id"], "chemical"),
                       "electrical": con.degree(node["id"], "electrical"),
                       "all": con.degree(node["id"], "all")},
            "in_chemical": con.in_edges(node["id"], "chemical"),
            "out_chemical": con.out_edges(node["id"], "chemical"),
            "in_electrical": con.in_edges(node["id"], "electrical"),
            "out_electrical": con.out_edges(node["id"], "electrical")}


@app.get("/api/connections")
def list_connections(dataset_id: str, source: str | None = None, target: str | None = None,
                     kind: str = "all", limit: int = Query(50, le=500), offset: int = 0):
    ds = dataset_or_404(dataset_id)
    edges = ds["edges"]
    if kind != "all":
        edges = [e for e in edges if e.get("kind") == kind]
    if source:
        edges = [e for e in edges if e["source"] == source.upper()]
    if target:
        edges = [e for e in edges if e["target"] == target.upper()]
    return {"total": len(edges), "connections": edges[offset:offset + limit]}


@app.get("/api/graph/subgraph")
def get_subgraph(dataset_id: str, seeds: str, depth: int = Query(1, le=3),
                 direction: str = "both", kind: str = "all"):
    con = get_connectome(dataset_id)
    if direction not in ("in", "out", "both"):
        raise HTTPException(422, "direction must be in|out|both")
    return con.subgraph([s.strip().upper() for s in seeds.split(",") if s.strip()],
                        depth, direction, kind, MAX_SUBGRAPH_NODES)


@app.get("/api/graph/stats")
def graph_stats(dataset_id: str):
    con = get_connectome(dataset_id)
    return {"dataset_id": dataset_id, "n_nodes": len(con.nodes), "n_edges": len(con.edges),
            "hubs": con.hub_scores(top=10)}

# ---------------------------------------------------------------- experiments
@app.get("/api/experiments")
def list_experiments(limit: int = Query(50, le=200), offset: int = 0,
                     author: str | None = None):
    files = list_experiment_files()
    seen = {f.stem for f in files}
    records = []
    for f in files:
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    # shared KV records not already present as files (KV wins on conflict)
    by_id = {r.get("experiment_id"): r for r in records}
    for eid in kv_exp_ids():
        if eid not in by_id:
            rec = kv_exp_get(eid)
            if rec:
                by_id[eid] = rec
    records = sorted(by_id.values(), key=lambda r: r.get("experiment_id", ""))
    if author:
        records = [r for r in records if (r.get("author") or "") == author]
    items = [{k: r.get(k) for k in
              ("experiment_id", "research_question", "species", "dataset_id",
               "model", "created_utc", "author")} for r in records[offset:offset + limit]]
    return {"total": len(records), "experiments": items}


def _next_counter() -> int:
    kv = _kv()
    if kv:
        try:
            if kv.pipe([["GET", "nl:exp:counter"]])[0] is None:
                nums = [1]
                for f in list_experiment_files():
                    try:
                        nums.append(int(f.stem.split("-")[-1]))
                    except ValueError:
                        pass
                for eid in kv_exp_ids():
                    try:
                        nums.append(int(eid.split("-")[-1]))
                    except ValueError:
                        pass
                # SET NX: only the first concurrent caller seeds; INCR below
                # still yields a unique number for everyone.
                kv.pipe([["SET", "nl:exp:counter", max(nums), "NX"]])
            return int(kv.pipe([["INCR", "nl:exp:counter"]])[0])
        except (HTTPException, KeyError, TypeError, ValueError):
            pass
    for cand in (EXP_DIR / "_counter.json", EXP_DIR_ROOT / "_counter.json"):
        try:
            if cand.exists():
                return int(json.loads(cand.read_text(encoding="utf-8"))["counter"]) + 1
        except Exception:
            continue
    # fallback: derive from existing experiment files (serverless-safe)
    try:
        nums = [int(f.stem.split("-")[-1]) for f in list_experiment_files()]
        return max(nums, default=1) + 1
    except Exception:
        return 2


@app.post("/api/experiments", status_code=201)
def create_experiment(payload: dict, x_role: str | None = Header(None),
                      authorization: str | None = Header(None)):
    require_researcher(x_role)
    if not payload.get("dataset_id"):
        raise HTTPException(422, "dataset_id required")
    ds = dataset_or_404(payload["dataset_id"])
    try:
        validate_experiment(payload, ds, MODEL_REGISTRY)
    except ValueError as e:
        raise HTTPException(422, str(e))
    counter = _next_counter()
    exp_id = new_experiment_id(counter)
    meta = registry_entry(payload["dataset_id"])
    if meta is None:
        doc = dataset_or_404(payload["dataset_id"])
        meta = {"version": doc.get("version", "1.0.0-import"),
                "source": doc.get("source", "user upload"),
                "publication": doc.get("publication"),
                "license": doc.get("license", "user-provided"),
                "citation": doc.get("citation"),
                "completeness": doc.get("completeness", ""),
                "limitations": doc.get("limitations", "")}
    record = experiment_to_dict(exp_id, payload, meta, ENGINE_VERSION,
                                MODEL_REGISTRY[payload["model"]].version)
    # sign with the campus account when the caller is logged in
    try:
        from backend.app.campus import current_user as _campus_user
        _, _display = _campus_user(authorization)
        record["author"] = _display
    except Exception:
        pass
    save_experiment(record)
    kv = _kv()
    if not kv:
        try:
            (EXP_DIR / "_counter.json").write_text(json.dumps({"counter": counter}),
                                                   encoding="utf-8")
        except Exception:
            pass
    return {"experiment_id": exp_id, "record": record}


@app.get("/api/experiments/{exp_id}")
def get_experiment(exp_id: str):
    return read_experiment(exp_id.upper())


@app.post("/api/simulations")
def post_simulation(body: dict, x_role: str | None = Header(None)):
    require_researcher(x_role)
    record = read_experiment(body.get("experiment_id", "").upper())
    steps = len(get_connectome(record["dataset_id"]).nodes) * int(record.get("duration_ms", 0))
    if steps > MAX_SIM_STEPS:
        raise HTTPException(413, f"circuit too large for this duration "
                                 f"({steps} neuron-steps > {MAX_SIM_STEPS}): shorten "
                                 f"duration_ms or import a smaller circuit")
    record = simulate_experiment(record)
    save_experiment(record)
    return {"experiment_id": record["experiment_id"], "comparison": record["results"]["comparison"],
            "normal_total": record["results"]["normal"]["summary"]["total_spikes"],
            "modified_total": record["results"]["modified"]["summary"]["total_spikes"]}


@app.get("/api/results/{exp_id}")
def get_results(exp_id: str):
    record = read_experiment(exp_id.upper())
    if "results" not in record:
        raise HTTPException(409, "not simulated yet: POST /api/simulations first")
    return record["results"]


@app.get("/api/reports/{exp_id}")
def get_report(exp_id: str):
    r = read_experiment(exp_id.upper())
    c = (r.get("results") or {}).get("comparison", {})
    return {
        "title": f"Experimental Report {r['experiment_id']}",
        "disclaimer": "COMPUTATIONAL SIMULATION — not biological evidence.",
        "research_question": r.get("research_question"),
        "dataset": {k: r.get(k) for k in ("dataset_id", "dataset_version")},
        "model": {"name": r.get("model"), "version": r.get("model_version"),
                  "parameters": r.get("parameters")},
        "virtual_manipulation": r.get("manipulations_virtual_only"),
        "stimulus": r.get("stimulus"), "duration_ms": r.get("duration_ms"),
        "seed": r.get("seed"), "engine_version": r.get("engine_version"),
        "results": {"normal_total": (r.get("results") or {}).get("normal", {})
                    .get("summary", {}).get("total_spikes"),
                    "modified_total": (r.get("results") or {}).get("modified", {})
                    .get("summary", {}).get("total_spikes"),
                    "comparison": c},
        "limitations": (r.get("dataset_provenance") or {}).get("limitations"),
        "reproducibility": {k: r.get(k) for k in ("experiment_id", "seed", "engine_version",
                                                 "created_utc", "dataset_version", "model_version")},
        "references": [(r.get("dataset_provenance") or {}).get("publication"),
                       (r.get("dataset_provenance") or {}).get("citation")],
    }


@app.get("/api/provenance/{exp_id}")
def get_provenance(exp_id: str):
    r = read_experiment(exp_id.upper())
    prov = r.get("dataset_provenance", {})
    return {"experiment_id": r["experiment_id"],
            "chain": [
                {"stage": "Dataset", "value": r.get("dataset_id")},
                {"stage": "Version", "value": r.get("dataset_version")},
                {"stage": "Source", "value": prov.get("source")},
                {"stage": "Publication", "value": prov.get("publication")},
                {"stage": "Transformation",
                 "value": "bundled reference subset (textbook topology, unweighted) "
                          "— full Varshney matrix via scripts/ingest_varshney.py"},
                {"stage": "Simulation",
                 "value": f"{r.get('model')} {r.get('model_version')} / engine "
                          f"{r.get('engine_version')} / seed {r.get('seed')}"},
                {"stage": "Result",
                 "value": "normal vs modified summaries" if "results" in r else "not simulated yet"},
            ]}

# ---------------------------------------------------------------- AI assistant (rule-based, labelled)
@app.post("/api/ai/explain")
def ai_explain(body: dict):
    question = (body.get("question") or "").strip()
    ds_id = body.get("dataset_id", "c_elegans_reference_circuit")
    neuron_id = (body.get("neuron_id") or "").upper() or None
    exp_id = (body.get("experiment_id") or "").upper() or None
    if ds_id not in _datasets:
        raise HTTPException(404, f"unknown dataset '{ds_id}'")
    con = _connectomes[ds_id]
    lines = []
    if neuron_id:
        node = con.get(neuron_id)
        if not node:
            raise HTTPException(404, f"unknown neuron '{neuron_id}'")
        deg = con.degree(neuron_id, "chemical")
        lines.append(f"[FACT] {neuron_id}: type={node.get('type')}, class={node.get('class')}, "
                     f"region={node.get('region')}, function-note='{node.get('function')}'. "
                     f"Chemical degree in this dataset: in={deg['in']}, out={deg['out']}.")
        ins = [e["source"] for e in con.in_edges(neuron_id, "chemical")]
        outs = [e["target"] for e in con.out_edges(neuron_id, "chemical")]
        lines.append(f"[FACT] Incoming from: {ins or 'none in this dataset'}. "
                     f"Outgoing to: {outs or 'none in this dataset'}.")
        lines.append("[INTERPRETATION] Dans ce modèle, ce neurone est un nœud du circuit de "
                     "retrait au toucher ; toute affirmation sur son rôle chez l'animal exigerait "
                     "une source expérimentale (cf. Chalfie et al. 1985).")
    elif "hub" in question.lower() or "connect" in question.lower():
        hubs = con.hub_scores(top=5)
        lines.append("[FACT] Neurones les plus connectés (degré total, ce dataset): " +
                     ", ".join(f"{h['neuron']} ({h['degree']})" for h in hubs) + ".")
        lines.append("[HYPOTHESIS] Ces hubs sont de bons candidats pour des manipulations "
                     "virtuelles (silence/activation) afin d'observer la propagation dans le modèle.")
    elif "dataset" in question.lower() or "données" in question.lower() or not question:
        meta = registry_entry(ds_id)
        lines.append(f"[FACT] Dataset '{ds_id}' v{meta['version']}: {meta['name']}. "
                     f"{meta['completeness']} Limites: {meta['limitations']}")
    if exp_id:
        try:
            r = read_experiment(exp_id)
            if "results" in r:
                c = r["results"]["comparison"]
                lines.append(f"[SIMULATION RESULT] {exp_id}: normal="
                             f"{r['results']['normal']['summary']['total_spikes']} spikes vs "
                             f"modified={r['results']['modified']['summary']['total_spikes']} "
                             f"({c.get('pct_total')}% total). Biais comportemental (proxy modèle) "
                             f"Δ={c.get('behavior_delta')}. Seed {r.get('seed')}, "
                             f"moteur {r.get('engine_version')}.")
            else:
                lines.append(f"[FACT] {exp_id} existe mais n'a pas encore été simulée.")
        except HTTPException:
            lines.append(f"[FACT] Expérience {exp_id} introuvable.")
    if not lines:
        lines.append("[FACT] Je raisonne uniquement sur les données de la plateforme. "
                     "Donnez neuron_id, experiment_id, ou interrogez hubs/dataset.")
        lines.append("[HYPOTHESIS] Exemple d'expérience: inhiber virtuellement PVCL puis comparer "
                     "la propagation postérieure (cf. NL-EXP-000001).")
    return {"answer": "\n".join(lines),
            "caution": "AI interpretation — verify against data and cited publications."}

# ---------------------------------------------------------------- export + pages
@app.get("/api/export/{exp_id}.json")
def export_json(exp_id: str):
    return read_experiment(exp_id.upper())


@app.get("/api/export/{exp_id}.csv")
def export_csv(exp_id: str):
    r = read_experiment(exp_id.upper())
    if "results" not in r:
        raise HTTPException(409, "not simulated yet")
    buf = io.StringIO()
    buf.write(f"# experiment {r['experiment_id']} | dataset {r['dataset_id']} "
              f"v{r.get('dataset_version')} | model {r.get('model')} {r.get('model_version')} "
              f"| seed {r.get('seed')} | engine {r.get('engine_version')} "
              f"| COMPUTATIONAL SIMULATION\n")
    w = csv.writer(buf)
    w.writerow(["neuron", "spikes_normal", "spikes_modified", "delta"])
    for row in r["results"]["comparison"]["per_neuron"]:
        w.writerow([row["neuron"], row["normal"], row["modified"], row["delta"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@app.get("/experiment/{exp_id}", response_class=FileResponse)
def experiment_page(exp_id: str):
    return FileResponse(STATIC / "index.html")


@app.get("/openapi.json", include_in_schema=False)
def openapi_json():
    return JSONResponse(app.openapi())


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
