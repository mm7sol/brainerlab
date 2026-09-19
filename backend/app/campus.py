"""Campus — global university directory + representation.

- Directory: 10k+ universities from the bundled Hipolabs-derived index
  (data/universities/universities.json). Search server-side, paginated.
- Accounts: username + password (pbkdf2-sha256, stdlib), bearer sessions.
- Representation: one university per account; join switches affiliation.
- Leaderboard: universities ranked by member count.
- Persistence: shared KV when configured, JSON file otherwise
  (see campus_store + GET /api/campus/status).
"""
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query

from backend.app.campus_store import SESSION_TTL_S, get_store

router = APIRouter(prefix="/api/campus", tags=["campus"])

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = ROOT / "data" / "universities" / "universities.json"

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

_INDEX = None


def get_index():
    global _INDEX
    if _INDEX is None:
        doc = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        unis = doc["universities"]
        _INDEX = {"version": doc.get("version", "?"), "count": len(unis),
                  "by_id": {u["id"]: u for u in unis}, "all": unis}
    return _INDEX


def search_universities(all_unis, q=None, country=None, limit=20, offset=0):
    q = (q or "").strip().casefold()
    out = all_unis
    if country:
        out = [u for u in out if u.get("country") == country]
    if q:
        out = [u for u in out
               if q in (u.get("name") or "").casefold()
               or q in (u.get("domain") or "").casefold()]
    else:
        out = sorted(out, key=lambda u: u.get("name") or "")
    return out[offset:offset + limit], len(out)


def get_countries(all_unis):
    agg = {}
    for u in all_unis:
        c = u.get("country") or "Unknown"
        e = agg.setdefault(c, {"country": c, "universities": 0, "codes": {}})
        e["universities"] += 1
        if u.get("cc"):
            e["codes"][u["cc"]] = e["codes"].get(u["cc"], 0) + 1
    rows = [{"country": c, "universities": e["universities"],
             "code": max(e["codes"], key=e["codes"].get) if e["codes"] else None}
            for c, e in agg.items()]
    rows.sort(key=lambda r: (-r["universities"], r["country"]))
    return rows


# -- auth ------------------------------------------------------------------
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt.encode("utf-8"), 200_000).hex()
    return f"pbkdf2-sha256$200000${salt}${digest}"


def verify_password(password, stored):
    try:
        _, _, salt, _ = stored.split("$")
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def new_token():
    return secrets.token_hex(32)


def current_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "login required (Bearer token)")
    store = get_store()
    try:
        sess = store.session_get(authorization[7:])
    except Exception:
        raise HTTPException(503, "member store unavailable")
    if not sess or sess.get("created", 0) + SESSION_TTL_S < time.time():
        raise HTTPException(401, "session expired, login again")
    return sess["username"], sess.get("display", sess["username"])


def with_counts(entries):
    store = get_store()
    try:
        return [{**u, "members": store.count(u["id"])} for u in entries]
    except Exception:
        raise HTTPException(503, "member store unavailable")


# -- endpoints ---------------------------------------------------------------
@router.get("/status")
def status():
    idx = get_index()
    store = get_store()
    url_cfg = bool(os.environ.get("KV_REST_API_URL")
                   or os.environ.get("UPSTASH_REDIS_REST_URL"))
    try:
        total = store.total_members()
    except Exception:
        total = None
    try:
        from backend.app import main as _main
        exp_shared = _main._kv() is not None
    except Exception:
        exp_shared = False
    exp_backend = ("shared-kv" if exp_shared
                   else "ephemeral-tmp" if os.environ.get("VERCEL") == "1" else "local-file")
    return {"universities": idx["count"], "dataset_version": idx["version"],
            "backend": store.kind, "shared": url_cfg,
            "total_members": total,
            "experiments_backend": exp_backend, "experiments_shared": exp_shared,
            "note": None if url_cfg else
            "demo mode: configure Vercel KV (KV_REST_API_URL/TOKEN) for shared memberships"}


@router.get("/countries")
def countries():
    return {"countries": get_countries(get_index()["all"])}


@router.get("/universities")
def universities(q: str | None = None, country: str | None = None,
                 limit: int = Query(20, le=100), offset: int = 0):
    idx = get_index()
    page, total = search_universities(idx["all"], q, country, limit, offset)
    return {"total": total, "universities": with_counts(page)}


@router.get("/universities/{uid}")
def university(uid: str):
    u = get_index()["by_id"].get(uid)
    if not u:
        raise HTTPException(404, f"unknown university '{uid}'")
    return with_counts([u])[0]


@router.post("/register", status_code=201)
def register(body: dict):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "username: 3-32 chars [a-zA-Z0-9_.-]")
    if len(password) < 6:
        raise HTTPException(422, "password: 6+ characters")
    store = get_store()
    record = {"display": username, "pass": hash_password(password),
              "created": time.time()}
    try:
        created = store.user_create_nx(username.lower(), record)
    except Exception:
        raise HTTPException(503, "member store unavailable")
    if not created:
        raise HTTPException(409, "username already taken")
    token = new_token()
    try:
        store.session_set(token, {"username": username.lower(), "display": username,
                                  "created": time.time()})
    except Exception:
        raise HTTPException(503, "member store unavailable")
    return {"token": token, "username": username}


@router.post("/login")
def login(body: dict):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    store = get_store()
    try:
        user = store.user_get(username.lower())
    except Exception:
        raise HTTPException(503, "member store unavailable")
    if not user or not verify_password(password, user.get("pass", "")):
        raise HTTPException(401, "invalid username or password")
    token = new_token()
    try:
        store.session_set(token, {"username": username.lower(),
                                  "display": user.get("display", username),
                                  "created": time.time()})
    except Exception:
        raise HTTPException(503, "member store unavailable")
    return {"token": token, "username": user.get("display", username)}


@router.post("/logout")
def logout(authorization: str | None = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        try:
            get_store().session_del(authorization[7:])
        except Exception:
            pass
    return {"ok": True}


@router.get("/me")
def me(authorization: str | None = Header(None)):
    key, display = current_user(authorization)
    store = get_store()
    try:
        uid = store.membership_get(key)
    except Exception:
        raise HTTPException(503, "member store unavailable")
    uni = get_index()["by_id"].get(uid) if uid else None
    if uni:
        uni = {**uni, "members": store.count(uid)}
    return {"username": display, "university": uni}


@router.post("/join")
def join(body: dict, authorization: str | None = Header(None)):
    key, display = current_user(authorization)
    uid = body.get("university_id")
    if get_index()["by_id"].get(uid) is None:
        raise HTTPException(404, f"unknown university '{uid}'")
    store = get_store()
    try:
        old = store.membership_set(key, uid)
        u = {**get_index()["by_id"][uid], "members": store.count(uid)}
    except Exception:
        raise HTTPException(503, "member store unavailable")
    return {"username": display, "university": u, "previous": old,
            "switched": bool(old and old != uid)}


@router.post("/leave")
def leave(authorization: str | None = Header(None)):
    key, display = current_user(authorization)
    store = get_store()
    try:
        old = store.membership_clear(key)
    except Exception:
        raise HTTPException(503, "member store unavailable")
    return {"username": display, "left": old}


@router.get("/leaderboard")
def leaderboard(limit: int = Query(20, le=100), offset: int = 0):
    idx = get_index()
    store = get_store()
    try:
        ranked = store.top(limit, offset)
        total = store.total_members()
    except Exception:
        raise HTTPException(503, "member store unavailable")
    rows = []
    for uid, n in ranked:
        u = idx["by_id"].get(uid)
        if u:
            rows.append({**u, "members": n})
    return {"total_members": total, "leaders": rows}


@router.get("/members")
def members(university_id: str, limit: int = Query(50, le=100)):
    if get_index()["by_id"].get(university_id) is None:
        raise HTTPException(404, f"unknown university '{university_id}'")
    store = get_store()
    try:
        keys = store.members_of(university_id, limit)
        names = []
        for k in keys:
            u = store.user_get(k) or {}
            names.append(u.get("display", k))
    except Exception:
        raise HTTPException(503, "member store unavailable")
    return {"university_id": university_id, "total": store.count(university_id),
            "members": names}
