"""Campus member store — shared persistence abstraction.

Two backends behind one interface:

- FileBackend: single JSON document, atomic replace. Used for local dev and
  as degraded ephemeral storage on serverless without KV configured.
- KvRestBackend: Upstash-compatible REST (also what Vercel KV exposes).
  Activated when KV_REST_API_URL/KV_REST_API_TOKEN or
  UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN are set. Atomic counters
  (ZINCRBY/INCRBY) and sets keep join/leave/leaderboard race-safe.

No new dependencies: stdlib + httpx (already required by the backend).
"""
import json
import os
import tempfile
from pathlib import Path

SESSION_TTL_S = 30 * 24 * 3600
PREFIX = "campus:"


def kv_config():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return url.rstrip("/"), token
    return None, None


class FileBackend:
    kind = "local-file"

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"users": {}, "sessions": {}, "memberships": {}, "counts": {}})

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"users": {}, "sessions": {}, "memberships": {}, "counts": {}}

    def _write(self, doc):
        tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=str(self.path.parent),
                                          encoding="utf-8")
        try:
            json.dump(doc, tmp)
            tmp.close()
            os.replace(tmp.name, self.path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    # -- users / sessions -------------------------------------------------
    def user_get(self, key):
        return self._read()["users"].get(key)

    def user_create_nx(self, key, record):
        doc = self._read()
        if key in doc["users"]:
            return False
        doc["users"][key] = record
        self._write(doc)
        return True

    def session_get(self, token):
        return self._read()["sessions"].get(token)

    def session_set(self, token, record):
        doc = self._read()
        doc["sessions"][token] = record
        self._write(doc)

    def session_del(self, token):
        doc = self._read()
        doc["sessions"].pop(token, None)
        self._write(doc)

    # -- memberships ------------------------------------------------------
    def membership_get(self, key):
        return self._read()["memberships"].get(key)

    def membership_set(self, key, univ_id):
        """Returns previous university id (or None). Switch-safe."""
        doc = self._read()
        old = doc["memberships"].get(key)
        if old == univ_id:
            return old
        doc["memberships"][key] = univ_id
        counts = doc["counts"]
        if old:
            counts[old] = max(0, counts.get(old, 1) - 1)
            if counts[old] == 0:
                del counts[old]
        counts[univ_id] = counts.get(univ_id, 0) + 1
        self._write(doc)
        return old

    def membership_clear(self, key):
        doc = self._read()
        old = doc["memberships"].pop(key, None)
        if old:
            counts = doc["counts"]
            counts[old] = max(0, counts.get(old, 1) - 1)
            if counts[old] == 0:
                del counts[old]
            self._write(doc)
        return old

    def count(self, univ_id):
        return self._read()["counts"].get(univ_id, 0)

    def top(self, limit, offset):
        counts = self._read()["counts"]
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[offset:offset + limit]

    def total_members(self):
        return len(self._read()["memberships"])

    def members_of(self, univ_id, limit):
        doc = self._read()
        out = [u for u, v in doc["memberships"].items() if v == univ_id]
        return sorted(out)[:limit]


class KvRestBackend:
    kind = "shared-kv"

    def __init__(self, url, token):
        import httpx
        self.url = url
        self.client = httpx.Client(headers={"Authorization": f"Bearer {token}"},
                                   timeout=10.0)

    def _pipe(self, commands):
        r = self.client.post(f"{self.url}/pipeline", json=commands)
        r.raise_for_status()
        body = r.json()
        if isinstance(body, dict) and "error" in body:
            raise RuntimeError(f"kv error: {body['error']}")
        return [item.get("result") for item in body]

    def pipe(self, commands):
        """Generic pipeline access (GET/SET/DEL/INCR/SADD/SMEMBERS/…)."""
        return self._pipe(commands)

    def _k(self, *parts):
        return PREFIX + ":".join(parts)

    # -- users / sessions -------------------------------------------------
    def user_get(self, key):
        res = self._pipe([["GET", self._k("user", key)]])[0]
        return json.loads(res) if res else None

    def user_create_nx(self, key, record):
        res = self._pipe([["SET", self._k("user", key), json.dumps(record), "NX"]])[0]
        return res == "OK"

    def session_get(self, token):
        res = self._pipe([["GET", self._k("session", token)]])[0]
        return json.loads(res) if res else None

    def session_set(self, token, record):
        self._pipe([["SET", self._k("session", token), json.dumps(record),
                     "EX", SESSION_TTL_S]])

    def session_del(self, token):
        self._pipe([["DEL", self._k("session", token)]])

    # -- memberships ------------------------------------------------------
    def membership_get(self, key):
        return self._pipe([["GET", self._k("membership", key)]])[0]

    def membership_set(self, key, univ_id):
        old = self.membership_get(key)
        if old == univ_id:
            return old
        cmds = [["SET", self._k("membership", key), univ_id],
                ["SADD", self._k("univ", univ_id), key],
                ["ZINCRBY", PREFIX + "board", 1, univ_id]]
        if old:
            cmds += [["SREM", self._k("univ", old), key],
                     ["ZINCRBY", PREFIX + "board", -1, old]]
        else:
            cmds.append(["INCRBY", PREFIX + "stat:members", 1])
        self._pipe(cmds)
        return old

    def membership_clear(self, key):
        old = self.membership_get(key)
        if not old:
            return None
        self._pipe([["DEL", self._k("membership", key)],
                    ["SREM", self._k("univ", old), key],
                    ["ZINCRBY", PREFIX + "board", -1, old],
                    ["INCRBY", PREFIX + "stat:members", -1]])
        return old

    def count(self, univ_id):
        res = self._pipe([["ZSCORE", PREFIX + "board", univ_id]])[0]
        try:
            return int(float(res)) if res is not None else 0
        except (TypeError, ValueError):
            return 0

    def top(self, limit, offset):
        res = self._pipe([["ZREVRANGE", PREFIX + "board", offset, offset + limit - 1,
                            "WITHSCORES"]])[0] or []
        it = iter(res)
        return [(uid, int(float(score))) for uid, score in zip(it, it)]

    def total_members(self):
        res = self._pipe([["GET", PREFIX + "stat:members"]])[0]
        try:
            return int(res) if res is not None else 0
        except (TypeError, ValueError):
            return 0

    def members_of(self, univ_id, limit):
        res = self._pipe([["SMEMBERS", self._k("univ", univ_id)]])[0] or []
        return sorted(res)[:limit]


_STORE = None


def get_store():
    """Singleton. KV when configured, otherwise a JSON file (repo locally,
    /tmp on serverless)."""
    global _STORE
    if _STORE is not None:
        return _STORE
    url, token = kv_config()
    if url and token:
        _STORE = KvRestBackend(url, token)
        return _STORE
    from backend.app.main import EXP_DIR  # local import: avoids cycles
    if os.environ.get("VERCEL") == "1":
        path = Path("/tmp/neurolab_campus.json")
    else:
        path = EXP_DIR.parent / "data" / "campus_store.json" \
            if (EXP_DIR.parent / "data").exists() else EXP_DIR / "campus_store.json"
    _STORE = FileBackend(path)
    _STORE.kind = "ephemeral-tmp" if os.environ.get("VERCEL") == "1" else "local-file"
    return _STORE


def reset_store():
    global _STORE
    _STORE = None
