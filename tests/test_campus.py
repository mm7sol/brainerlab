"""Campus tests (stdlib unittest, offline). Run: python tests/test_campus.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app import campus
from backend.app import campus_store


class TestIndex(unittest.TestCase):
    def test_index_integrity(self):
        idx = campus.get_index()
        self.assertGreater(idx["count"], 9000)
        self.assertEqual(len(idx["by_id"]), idx["count"])
        for u in idx["all"][:500]:
            self.assertTrue(u["id"] and u["name"] and u["country"])

    def test_countries_cover_globe(self):
        rows = campus.get_countries(campus.get_index()["all"])
        self.assertGreater(len(rows), 150)
        names = {r["country"] for r in rows}
        self.assertTrue({"France", "United States", "Japan"} <= names)
        self.assertEqual(sum(r["universities"] for r in rows), campus.get_index()["count"])

    def test_search(self):
        all_u = campus.get_index()["all"]
        page, total = campus.search_universities(all_u, q="sorbonne")
        self.assertGreater(total, 0)
        self.assertTrue(all("sorbonne" in u["name"].casefold() for u in page))
        page2, total2 = campus.search_universities(all_u, country="France", limit=100)
        self.assertTrue(total2 > 100 and all(u["country"] == "France" for u in page2))

    def test_password_roundtrip(self):
        h = campus.hash_password("radium123")
        self.assertTrue(campus.verify_password("radium123", h))
        self.assertFalse(campus.verify_password("wrong", h))


class TestFileStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "campus.json"
        self.s = campus_store.FileBackend(self.tmp)

    def test_join_leave_leaderboard(self):
        self.assertTrue(self.s.user_create_nx("curie", {"display": "Curie"}))
        self.assertFalse(self.s.user_create_nx("curie", {"display": "Curie"}))
        self.assertIsNone(self.s.membership_set("curie", "u00001"))
        self.assertEqual(self.s.count("u00001"), 1)
        # switch affiliation: old decremented, new incremented
        self.assertEqual(self.s.membership_set("curie", "u00002"), "u00001")
        self.assertEqual(self.s.count("u00001"), 0)
        self.assertEqual(self.s.count("u00002"), 1)
        self.assertEqual(self.s.top(5, 0), [("u00002", 1)])
        self.assertEqual(self.s.members_of("u00002", 10), ["curie"])
        self.assertEqual(self.s.membership_clear("curie"), "u00002")
        self.assertEqual(self.s.total_members(), 0)


class TestEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        campus_store._STORE = campus_store.FileBackend(
            Path(tempfile.mkdtemp()) / "campus.json")
        from backend.app.main import app
        cls.c = TestClient(app)

    def test_full_flow(self):
        c = self.c
        self.assertEqual(c.get("/api/campus/status").json()["universities"],
                         campus.get_index()["count"])
        r = c.post("/api/campus/register", json={"username": "Flow", "password": "secret12"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.post("/api/campus/register",
                                json={"username": "Flow", "password": "secret12"}).status_code, 409)
        h = {"Authorization": "Bearer " + r.json()["token"]}
        uid = c.get("/api/campus/universities?q=sorbonne&limit=1").json()["universities"][0]["id"]
        j = c.post("/api/campus/join", json={"university_id": uid}, headers=h)
        self.assertEqual(j.status_code, 200)
        self.assertEqual(c.get("/api/campus/me", headers=h).json()["username"], "Flow")
        board = c.get("/api/campus/leaderboard").json()
        self.assertEqual(board["total_members"], 1)
        self.assertEqual(board["leaders"][0]["id"], uid)
        self.assertIn("Flow", c.get("/api/campus/members",
                                    params={"university_id": uid}).json()["members"])
        self.assertEqual(c.post("/api/campus/leave", headers=h).status_code, 200)
        self.assertEqual(c.get("/api/campus/me", headers=h).json()["university"], None)

    def test_auth_guards(self):
        c = self.c
        self.assertEqual(c.post("/api/campus/join",
                                json={"university_id": "u00001"}).status_code, 401)
        self.assertEqual(c.post("/api/campus/register",
                                json={"username": "x", "password": "short"}).status_code, 422)
        self.assertEqual(c.get("/api/campus/universities/uXXXXX").status_code, 404)

    def test_experiment_author(self):
        c = self.c
        tok = c.post("/api/campus/register",
                     json={"username": "Author", "password": "secret12"}).json()["token"]
        body = {"species": "caenorhabditis_elegans", "dataset_id": "c_elegans_reference_circuit",
                "model": "lif", "parameters": {}, "duration_ms": 50, "seed": 1,
                "stimulus": [], "manipulations": {}, "research_question": "signed"}
        signed = c.post("/api/experiments", json=body,
                        headers={"Authorization": f"Bearer {tok}"}).json()
        anon = c.post("/api/experiments", json=body).json()
        self.assertEqual(c.get(f"/api/experiments/{signed['experiment_id']}").json()["author"], "Author")
        self.assertNotIn("author", c.get(f"/api/experiments/{anon['experiment_id']}").json())
        mine = c.get("/api/experiments", params={"author": "Author"}).json()
        self.assertIn(signed["experiment_id"], {e["experiment_id"] for e in mine["experiments"]})
        self.assertNotIn(anon["experiment_id"], {e["experiment_id"] for e in mine["experiments"]})


class FakeKV:
    """Minimal in-memory Upstash-REST subset for experiment-store tests."""
    kind = "shared-kv"

    def __init__(self):
        self.kv = {}
        self.sets = {}

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
            elif op == "SADD":
                self.sets.setdefault(cmd[1], set()).add(cmd[2])
                out.append(1)
            elif op == "SMEMBERS":
                out.append(sorted(self.sets.get(cmd[1], set())))
            elif op == "DEL":
                out.append(1 if self.kv.pop(cmd[1], None) is not None else 0)
            else:
                raise AssertionError(f"unsupported op {op}")
        return out

    # campus_store interface stubs (unused here, keep isinstance checks valid)
    def user_get(self, k): raise AssertionError("unused")
    def user_create_nx(self, k, r): raise AssertionError("unused")
    def session_get(self, t): raise AssertionError("unused")
    def session_set(self, t, r): raise AssertionError("unused")
    def session_del(self, t): raise AssertionError("unused")
    def membership_get(self, k): raise AssertionError("unused")
    def membership_set(self, k, u): raise AssertionError("unused")
    def membership_clear(self, k): raise AssertionError("unused")
    def count(self, u): raise AssertionError("unused")
    def top(self, l, o): raise AssertionError("unused")
    def total_members(self): raise AssertionError("unused")
    def members_of(self, u, l): raise AssertionError("unused")


class TestExperimentKV(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend.app.main as main
        from fastapi.testclient import TestClient
        cls.fake = FakeKV()
        cls._orig = main._kv
        main._kv = lambda: cls.fake
        cls.c = TestClient(main.app)
        cls.main = main

    @classmethod
    def tearDownClass(cls):
        cls.main._kv = cls._orig

    def test_create_simulate_list_counters(self):
        c = self.c
        body = {"species": "caenorhabditis_elegans",
                "dataset_id": "c_elegans_reference_circuit", "model": "lif",
                "parameters": {}, "duration_ms": 50, "seed": 7,
                "stimulus": [], "manipulations": {},
                "research_question": "kv smoke"}
        r1 = c.post("/api/experiments", json=body)
        self.assertEqual(r1.status_code, 201)
        id1 = r1.json()["experiment_id"]
        r2 = c.post("/api/experiments", json=body)
        id2 = r2.json()["experiment_id"]
        self.assertNotEqual(id1, id2)
        # simulate first, read back with results
        s = c.post("/api/simulations", json={"experiment_id": id1})
        self.assertEqual(s.status_code, 200)
        got = c.get(f"/api/experiments/{id1}").json()
        self.assertIn("results", got)
        # listing merges KV records
        lst = c.get("/api/experiments?limit=200").json()
        ids = {e["experiment_id"] for e in lst["experiments"]}
        self.assertTrue({id1, id2} <= ids)
        # status reports shared experiments backend
        st = c.get("/api/campus/status").json()
        self.assertTrue(st["experiments_shared"])
        self.assertEqual(st["experiments_backend"], "shared-kv")


if __name__ == "__main__":
    unittest.main(verbosity=1)
