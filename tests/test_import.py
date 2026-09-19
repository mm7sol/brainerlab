"""Dataset-import tests (stdlib unittest, offline). Run: python tests/test_import.py"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import main


class TestValidation(unittest.TestCase):
    def test_normalizes_ids(self):
        nodes, edges = main.validate_import_doc(
            [{"id": "a", "type": "sensory"}, {"id": "B"}],
            [{"source": "a", "target": "b", "kind": "electrical"}])
        self.assertEqual([n["id"] for n in nodes], ["A", "B"])
        self.assertEqual(edges[0]["kind"], "electrical")

    def test_rejects(self):
        bad = [
            ([], []),
            ([{"id": f"N{i}"} for i in range(10001)], []),
            ([{"id": "A"}, {"id": "B"}], [{"source": "A", "target": "B"}] * 100001),
            ([{"id": "A"}], [{"source": "A", "target": "Z"}]),
            ([{"id": "A", "type": "glia"}], []),
            ([{"id": "A"}, {"id": "a"}], []),
            ([{"nope": 1}], []),
            ([{"id": "A"}], [{"source": "A", "target": "A", "kind": "gap"}]),
        ]
        for nodes, edges in bad:
            with self.assertRaises(ValueError):
                main.validate_import_doc(nodes, edges)


class TestEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        cls.c = TestClient(main.app)

    def test_full_flow(self):
        c = self.c
        doc = {"name": "Trio", "species": "custom",
               "nodes": [{"id": "n1", "type": "sensory"}, {"id": "n2"},
                         {"id": "n3", "type": "motor", "region": "head"}],
               "edges": [{"source": "n1", "target": "n2"},
                         {"source": "N2", "target": "n3", "kind": "electrical"}]}
        r = c.post("/api/datasets/import", json=doc)
        self.assertEqual(r.status_code, 201)
        uid = r.json()["id"]
        self.assertTrue(uid.startswith("custom-trio-"))
        try:
            d = c.get(f"/api/datasets/{uid}").json()
            self.assertEqual(d["status"], "imported")
            self.assertEqual(d["bundled_nodes"], 3)
            self.assertIn("UNVERIFIED", d["completeness"])
            ids = sorted(n["id"] for n in
                         c.get("/api/neurons", params={"dataset_id": uid, "limit": 10}).json()["neurons"])
            self.assertEqual(ids, ["N1", "N2", "N3"])
            # usable in explorer + lab
            self.assertEqual(c.get("/api/graph/stats", params={"dataset_id": uid}).json()["n_edges"], 2)
            exp = c.post("/api/experiments",
                         json={"species": "custom", "dataset_id": uid, "model": "lif",
                               "parameters": {}, "duration_ms": 50, "seed": 1,
                               "stimulus": [{"neuron": "N1", "t_start_ms": 0, "t_end_ms": 10, "amplitude": 20}],
                               "manipulations": {}, "research_question": "t"}).json()
            sim = c.post("/api/simulations", json={"experiment_id": exp["experiment_id"]})
            self.assertEqual(sim.status_code, 200)
            # appears in selects (bundled counts set)
            all_ds = c.get("/api/datasets").json()["datasets"]
            self.assertIn(uid, {d["id"] for d in all_ds if d["bundled_nodes"]})
        finally:
            self.assertEqual(c.delete(f"/api/datasets/import/{uid}").json()["deleted"], uid)
        self.assertEqual(c.get(f"/api/datasets/{uid}").status_code, 404)

    def test_guards(self):
        c = self.c
        doc = {"name": "x", "nodes": [{"id": "A"}], "edges": []}
        self.assertEqual(c.post("/api/datasets/import", json=doc,
                                headers={"X-Role": "visitor"}).status_code, 403)
        self.assertEqual(c.delete("/api/datasets/import/c_elegans_reference_circuit").status_code, 404)
        self.assertEqual(c.delete("/api/datasets/import/custom-nope").status_code, 404)

    def test_csv_flow(self):
        c = self.c
        csv = "source,target,kind,weight\nAL,AR,chemical,5\nAR,BL\nBL,BR,electrical,2\n"
        r = c.post("/api/datasets/import", json={"name": "Csv", "csv": csv})
        self.assertEqual(r.status_code, 201)
        uid = r.json()["id"]
        try:
            self.assertEqual(r.json()["nodes"], 4)
            ids = sorted(n["id"] for n in
                         c.get("/api/neurons", params={"dataset_id": uid, "limit": 10}).json()["neurons"])
            self.assertEqual(ids, ["AL", "AR", "BL", "BR"])
            exp = c.post("/api/experiments",
                         json={"species": "custom", "dataset_id": uid, "model": "lif",
                               "parameters": {}, "duration_ms": 50, "seed": 1,
                               "stimulus": [{"neuron": "AL", "t_start_ms": 0, "t_end_ms": 10, "amplitude": 20}],
                               "manipulations": {}, "research_question": "t"}).json()
            self.assertEqual(c.post("/api/simulations",
                                    json={"experiment_id": exp["experiment_id"]}).status_code, 200)
        finally:
            c.delete(f"/api/datasets/import/{uid}")
        bad = c.post("/api/datasets/import", json={"name": "x", "csv": "source,target\nA,\n"})
        self.assertEqual(bad.status_code, 422)


    def test_sim_guard(self):
        c = self.c
        nodes = [{"id": f"G{i}"} for i in range(3000)]
        r = c.post("/api/datasets/import", json={"name": "Big", "nodes": nodes, "edges": []})
        self.assertEqual(r.status_code, 201)
        uid = r.json()["id"]
        try:
            exp = c.post("/api/experiments",
                         json={"species": "custom", "dataset_id": uid, "model": "lif",
                               "parameters": {}, "duration_ms": 300, "seed": 1,
                               "stimulus": [], "manipulations": {}, "research_question": "t"}).json()
            s = c.post("/api/simulations", json={"experiment_id": exp["experiment_id"]})
            self.assertEqual(s.status_code, 413)  # 3000 x 300 steps over budget
            exp2 = c.post("/api/experiments",
                          json={"species": "custom", "dataset_id": uid, "model": "lif",
                                "parameters": {}, "duration_ms": 100, "seed": 1,
                                "stimulus": [], "manipulations": {}, "research_question": "t"}).json()
            s2 = c.post("/api/simulations", json={"experiment_id": exp2["experiment_id"]})
            self.assertEqual(s2.status_code, 200)  # 3000 x 100 within budget
        finally:
            c.delete(f"/api/datasets/import/{uid}")


class FakeKV:
    """In-memory KV incl. hashes + chunked docs."""
    kind = "shared-kv"

    def __init__(self):
        self.kv = {}
        self.hashes = {}

    def pipe(self, commands):
        out = []
        for cmd in commands:
            op = cmd[0]
            if op == "GET":
                out.append(self.kv.get(cmd[1]))
            elif op == "SET":
                k, v = cmd[1], cmd[2]
                if "NX" in cmd and k in self.kv:
                    out.append(None)
                else:
                    self.kv[k] = v if isinstance(v, str) else json.dumps(v)
                    out.append("OK")
            elif op == "INCR":
                self.kv[cmd[1]] = str(int(self.kv.get(cmd[1], "0")) + 1)
                out.append(self.kv[cmd[1]])
            elif op == "DEL":
                out.append(1 if self.kv.pop(cmd[1], None) is not None else 0)
            elif op == "HSET":
                self.hashes.setdefault(cmd[1], {})[cmd[2]] = cmd[3]
                out.append(1)
            elif op == "HGETALL":
                flat = []
                for k, v in self.hashes.get(cmd[1], {}).items():
                    flat += [k, v]
                out.append(flat)
            elif op == "HDEL":
                out.append(1 if self.hashes.get(cmd[1], {}).pop(cmd[2], None) is not None else 0)
            else:
                raise AssertionError(f"unsupported op {op}")
        return out


class TestBrainImportKV(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        cls.fake = FakeKV()
        cls._orig_kv, cls._orig_chunk = main._kv, main.KV_CHUNK
        main._kv = lambda: cls.fake
        main.KV_CHUNK = 500  # force multi-chunk reassembly
        cls.c = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        main._kv = cls._orig_kv
        main.KV_CHUNK = cls._orig_chunk

    def test_chunked_roundtrip(self):
        c, fake = self.c, self.fake
        nodes = [{"id": f"K{i}", "type": "sensory", "region": "cortex-ish"} for i in range(60)]
        edges = [{"source": f"K{i}", "target": f"K{(i + 1) % 60}"} for i in range(60)]
        r = c.post("/api/datasets/import", json={"name": "Chunky", "nodes": nodes, "edges": edges})
        self.assertEqual(r.status_code, 201)
        uid = r.json()["id"]
        try:
            keys = [k for k in fake.kv if k.startswith(f"nl:ds:{uid}")]
            self.assertGreater(len(keys), 2)  # manifest + several chunks
            got = c.get(f"/api/datasets/{uid}").json()
            self.assertEqual(got["bundled_nodes"], 60)
            self.assertEqual(got["status"], "imported")
            ids = [n["id"] for n in
                   c.get("/api/neurons", params={"dataset_id": uid, "limit": 100}).json()["neurons"]]
            self.assertIn("K0", ids)
            all_ds = c.get("/api/datasets").json()["datasets"]
            self.assertIn(uid, {d["id"] for d in all_ds})
        finally:
            self.assertEqual(c.delete(f"/api/datasets/import/{uid}").json()["deleted"], uid)
        left = [k for k in list(fake.kv) + list(fake.hashes.get("nl:ds:meta", {})) if uid in k]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
