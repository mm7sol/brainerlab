"""BrainerLab tests (stdlib unittest, offline). Run: python tests/test_all.py"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.neurolab_engine import (Connectome, MODEL_REGISTRY, get_model, run_simulation,
                                    summarise, compare, new_experiment_id, validate_experiment,
                                    ENGINE_VERSION)

REF = ROOT / "data" / "processed" / "c_elegans_reference_circuit_v1.json"
REG = json.loads((ROOT / "data" / "registry" / "datasets.json").read_text(encoding="utf-8"))

STIM = [{"neuron": "PLML", "t_start_ms": 10, "t_end_ms": 60, "amplitude": 50.0},
        {"neuron": "PLMR", "t_start_ms": 10, "t_end_ms": 60, "amplitude": 50.0}]


def load_ref():
    return json.loads(REF.read_text(encoding="utf-8"))


class TestRegistry(unittest.TestCase):
    def test_required_keys(self):
        req = {"id", "species", "version", "source", "publication", "license",
               "neurons", "synapses", "completeness", "limitations"}
        # source/publication may be null for stubs — key must exist
        for d in REG["datasets"]:
            self.assertTrue(req <= set(d), f"missing keys in {d.get('id')}")
        ids = [d["id"] for d in REG["datasets"]]
        self.assertIn("c_elegans_reference_circuit", ids)
        self.assertIn("drosophila_flywire_fafb783", ids)

    def test_four_species(self):
        sp = {s["id"] for s in REG["species"]}
        self.assertEqual(sp, {"caenorhabditis_elegans", "drosophila_melanogaster",
                              "danio_rerio", "mus_musculus"})

    def test_no_whole_brain_mouse_claim(self):
        mouse = next(d for d in REG["datasets"] if d["species"] == "mus_musculus")
        self.assertIn("whole-brain", mouse["limitations"].lower())


class TestIngestion(unittest.TestCase):
    def test_reference_file_matches_builder(self):
        doc = load_ref()
        self.assertEqual(len(doc["nodes"]), 16)
        self.assertEqual(len(doc["edges"]), 23)
        self.assertTrue(all(e["weight"] is None for e in doc["edges"]))
        self.assertIn("ILLUSTRATIVE SUBSET", doc["completeness"])

    def test_varshney_bundled_matrix(self):
        p = ROOT / "data" / "processed" / "c_elegans_varshney2011_v1.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(len(doc["nodes"]), 281)  # 280 neurons + BWM
        chem = [e for e in doc["edges"] if e["kind"] == "chemical"]
        elec = [e for e in doc["edges"] if e["kind"] == "electrical"]
        self.assertEqual(len([e for e in chem if e["target"] != "BWM"]), 2194)
        self.assertEqual(len(elec), 1031)
        self.assertEqual(sum(e["weight"] for e in elec), 1777)
        self.assertTrue(all(e["weight"] is not None for e in doc["edges"]))
        con = Connectome(doc)
        self.assertEqual(len(con.nodes), 281)

    def test_courtship_subset(self):
        p = ROOT / "data" / "processed" / "drosophila_courtship_subset_v1.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(len(doc["nodes"]), 9)
        self.assertEqual(len(doc["edges"]), 9)
        self.assertTrue(all(e["weight"] is None for e in doc["edges"]))
        self.assertTrue(all(e["sign"] in (+1, -1) for e in doc["edges"]))
        self.assertIn("NOT measured connectivity", doc["completeness"])
        ids = {n["id"] for n in doc["nodes"]}
        self.assertTrue({"P1", "MAL", "VAB3"} <= ids)
        for e in doc["edges"]:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)
        p1 = next(n for n in doc["nodes"] if n["id"] == "P1")
        self.assertEqual(p1["dimorphism"], "male-specific")


class TestGraph(unittest.TestCase):
    def test_degrees_and_search(self):
        con = Connectome(load_ref())
        deg = con.degree("AVAL", "chemical")
        self.assertGreaterEqual(deg["in"], 3)
        self.assertGreaterEqual(deg["out"], 1)
        self.assertEqual(con.degree("DA1", "chemical")["out"], 0)

    def test_subgraph_depth_direction(self):
        con = Connectome(load_ref())
        g1 = con.subgraph(["PLML"], depth=1, direction="out")
        self.assertEqual({n["id"] for n in g1["nodes"]}, {"PLML", "PVCL"})
        g2 = con.subgraph(["DA1"], depth=1, direction="in")
        self.assertIn("AVAL", {n["id"] for n in g2["nodes"]})
        self.assertNotIn("VB1", {n["id"] for n in g2["nodes"]})

    def test_hubs(self):
        con = Connectome(load_ref())
        hubs = con.hub_scores(top=3)
        self.assertEqual(len(hubs), 3)
        self.assertGreaterEqual(hubs[0]["degree"], hubs[-1]["degree"])


class TestModels(unittest.TestCase):
    def test_unknown_model(self):
        with self.assertRaises(ValueError):
            get_model("hodgkin_huxley_fancy")

    def test_unknown_param_rejected(self):
        with self.assertRaises(ValueError):
            get_model("lif", {"magic": 1.0})

    def test_all_models_run(self):
        con = Connectome(load_ref())
        for m in MODEL_REGISTRY:
            out = run_simulation(con, m, {}, 50, STIM, None, seed=1)
            self.assertIn("PLML", out["spikes"])


class TestSimulation(unittest.TestCase):
    def test_determinism_same_seed(self):
        con = Connectome(load_ref())
        a = run_simulation(con, "lif", {}, 200, STIM, {"silence": ["PVCL"]}, seed=42)
        b = run_simulation(con, "lif", {}, 200, STIM, {"silence": ["PVCL"]}, seed=42)
        self.assertEqual(a["spikes"], b["spikes"])

    def test_manipulation_changes_result(self):
        con = Connectome(load_ref())
        n = run_simulation(con, "lif", {}, 200, STIM, None, seed=42)
        m = run_simulation(con, "lif", {}, 200, STIM, {"silence": ["PVCL", "PVCR"]}, seed=42)
        sn, sm = summarise(n["spikes"], 200), summarise(m["spikes"], 200)
        c = compare(sn, sm)
        self.assertLessEqual(sm["total_spikes"], sn["total_spikes"])
        self.assertNotEqual(c["delta_total"], 0)

    def test_reference_experiment_values(self):
        # golden values for NL-EXP-000001 (lif, seed 42, 200ms, PVCL silenced)
        con = Connectome(load_ref())
        n = run_simulation(con, "lif", {}, 200, STIM, None, seed=42)
        m = run_simulation(con, "lif", {}, 200, STIM, {"silence": ["PVCL"]}, seed=42)
        sn, sm = summarise(n["spikes"], 200), summarise(m["spikes"], 200)
        self.assertGreater(sn["total_spikes"], 0)
        self.assertLess(sm["total_spikes"], sn["total_spikes"])
        print(f"\n[golden] normal={sn['total_spikes']} modified={sm['total_spikes']} "
              f"delta={sm['total_spikes'] - sn['total_spikes']}")


class TestReproducibility(unittest.TestCase):
    def test_id_format(self):
        self.assertEqual(new_experiment_id(184), "NL-EXP-000184")

    def test_validation_rejects_unknown_neuron(self):
        doc = load_ref()
        bad = {"species": "caenorhabditis_elegans", "dataset_id": doc["id"], "model": "lif",
               "duration_ms": 100, "stimulus": [{"neuron": "NOPE", "t_start_ms": 0,
                                                 "t_end_ms": 5, "amplitude": 1.0}]}
        with self.assertRaises(ValueError):
            validate_experiment(bad, doc, MODEL_REGISTRY)

    def test_validation_rejects_bad_duration(self):
        doc = load_ref()
        bad = {"species": "caenorhabditis_elegans", "dataset_id": doc["id"], "model": "lif",
               "duration_ms": -5}
        with self.assertRaises(ValueError):
            validate_experiment(bad, doc, MODEL_REGISTRY)


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        cls.c = TestClient(app)

    def test_species_datasets(self):
        self.assertEqual(len(self.c.get("/api/species").json()["species"]), 4)
        ds = self.c.get("/api/datasets").json()["datasets"]
        self.assertGreaterEqual(len(ds), 7)

    def test_neuron_search_and_detail(self):
        r = self.c.get("/api/neurons?dataset_id=c_elegans_reference_circuit&q=ava").json()
        self.assertGreaterEqual(r["total"], 2)
        d = self.c.get("/api/neurons/AVAL?dataset_id=c_elegans_reference_circuit").json()
        self.assertEqual(d["neuron"]["id"], "AVAL")
        self.assertIn("degree", d)

    def test_subgraph_cap(self):
        g = self.c.get("/api/graph/subgraph?dataset_id=c_elegans_reference_circuit"
                        "&seeds=PLML,ALML&depth=3").json()
        self.assertLessEqual(len(g["nodes"]), 400)

    def test_experiment_lifecycle(self):
        body = {"species": "caenorhabditis_elegans", "dataset_id": "c_elegans_reference_circuit",
                "model": "lif", "duration_ms": 100, "seed": 7, "stimulus": STIM,
                "manipulations": {"silence": ["PVCR"]}}
        eid = self.c.post("/api/experiments", json=body,
                           headers={"X-Role": "researcher"}).json()["experiment_id"]
        self.assertTrue(eid.startswith("NL-EXP-"))
        sim = self.c.post("/api/simulations", json={"experiment_id": eid},
                           headers={"X-Role": "researcher"}).json()
        self.assertIn("comparison", sim)
        res = self.c.get(f"/api/results/{eid}").json()
        self.assertIn("normal", res)
        rep = self.c.get(f"/api/reports/{eid}").json()
        self.assertIn("COMPUTATIONAL", rep["disclaimer"])
        prov = self.c.get(f"/api/provenance/{eid}").json()
        self.assertEqual(len(prov["chain"]), 7)
        csv_txt = self.c.get(f"/api/export/{eid}.csv").text
        self.assertIn("spikes_normal", csv_txt)
        # determinism: re-simulate -> identical totals
        sim2 = self.c.post("/api/simulations", json={"experiment_id": eid},
                            headers={"X-Role": "researcher"}).json()
        self.assertEqual(sim["normal_total"], sim2["normal_total"])

    def test_bad_neuron_rejected(self):
        body = {"species": "caenorhabditis_elegans", "dataset_id": "c_elegans_reference_circuit",
                "model": "lif", "duration_ms": 100,
                "manipulations": {"silence": ["BOGUS"]}}
        r = self.c.post("/api/experiments", json=body, headers={"X-Role": "researcher"})
        self.assertEqual(r.status_code, 422)

    def test_visitor_cannot_post(self):
        r = self.c.post("/api/experiments", json={}, headers={"X-Role": "visitor"})
        self.assertEqual(r.status_code, 403)

    def test_ai_labels(self):
        a = self.c.post("/api/ai/explain", json={"neuron_id": "AVAL"}).json()["answer"]
        self.assertIn("[FACT]", a)
        self.assertIn("[INTERPRETATION]", a)

    def test_reference_experiment_reproducible(self):
        stored = self.c.get("/api/experiments/NL-EXP-000001").json()
        before = stored["results"]["comparison"]["delta_total"]
        self.c.post("/api/simulations", json={"experiment_id": "NL-EXP-000001"},
                     headers={"X-Role": "researcher"})
        after = self.c.get("/api/experiments/NL-EXP-000001").json()["results"]["comparison"]["delta_total"]
        self.assertEqual(before, after)


class TestSecurity(unittest.TestCase):
    """Path-traversal + malformed-id regression tests (see SECURITY.md).

    dataset_id / experiment_id double as filenames (<dir>/<id>.json):
    anything but a plain slug must be rejected with 422 before any
    filesystem access, and must never delete, serve, or crash on files.
    """

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        cls.c = TestClient(app)

    def test_query_traversal_rejected(self):
        bad = ["../registry/datasets", "../../experiments/NL-EXP-000001",
               "..%2F..%2Fexperiments%2FNL-EXP-000001", "/etc/passwd",
               "", "a/b", "..", ".", "x" * 200]
        for ds in bad:
            r = self.c.get("/api/neurons", params={"dataset_id": ds})
            self.assertEqual(r.status_code, 422, ds)
            r = self.c.get("/api/graph/stats", params={"dataset_id": ds})
            self.assertEqual(r.status_code, 422, ds)

    def test_simulation_traversal_rejected(self):
        r = self.c.post("/api/simulations",
                        json={"experiment_id": "../../experiments/NL-EXP-000001"},
                        headers={"X-Role": "researcher"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/simulations", json={"experiment_id": None},
                        headers={"X-Role": "researcher"})
        self.assertEqual(r.status_code, 422)

    def test_delete_traversal_deletes_nothing(self):
        from backend.app.main import ROOT
        registry = ROOT / "data" / "registry" / "datasets.json"
        before = registry.read_text(encoding="utf-8")
        r = self.c.delete("/api/datasets/import/..%2Fregistry%2Fdatasets",
                          headers={"X-Role": "researcher"})
        self.assertIn(r.status_code, (404, 405, 422))
        self.assertEqual(registry.read_text(encoding="utf-8"), before)
        # app still healthy afterwards
        self.assertEqual(self.c.get("/api/species").status_code, 200)

    def test_store_sink_containment(self):
        import json as _json
        import tempfile
        from pathlib import Path as _Path
        from backend.app import main as _main
        sentinel = _Path(tempfile.gettempdir()) / "brainerlab_probe.json"
        sentinel.write_text(_json.dumps({"id": "PROBE"}), encoding="utf-8")
        try:
            # real escapes / subdirs: get must raise before touching anything;
            # delete must never raise and never delete anything outside its dir.
            from backend.app.main import ROOT as _ROOT
            canary = _ROOT / "data" / "registry" / "datasets.json"
            canary_before = canary.read_text(encoding="utf-8")
            for evil in ("../registry/datasets", "../../experiments/x",
                         "sub/dir"):
                with self.assertRaises(Exception, msg=evil):
                    _main.import_store_get(evil)
                _main.import_store_delete(evil)  # must not raise...
            self.assertEqual(canary.read_text(encoding="utf-8"), canary_before)
        finally:
            self.assertTrue(sentinel.exists())  # untouched no matter what
            sentinel.unlink(missing_ok=True)

    def test_malformed_stored_doc_is_422_not_500(self):
        import json as _json
        from backend.app.main import IMPORT_DIR_ROOT
        IMPORT_DIR_ROOT.mkdir(parents=True, exist_ok=True)
        probe = IMPORT_DIR_ROOT / "_probe_bad.json"
        probe.write_text(_json.dumps({"nope": True}), encoding="utf-8")
        try:
            r = self.c.get("/api/neurons", params={"dataset_id": "_probe_bad"})
            self.assertEqual(r.status_code, 422)
        finally:
            probe.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
