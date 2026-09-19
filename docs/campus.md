# Campus — global university directory + representation

## Data

`data/universities/universities.json` (v`hipo-2026-09`): 10 259 universities,
201 countries, derived from the Hipo `university-domains-list`
(world_universities_and_domains.json), sorted by (country, name) with stable
ids (`u00001`…). Only id, name, country, alpha-2 code, first domain and first
web page are kept (1.7 MB). Search is server-side and paginated — the file is
never shipped to the browser.

## API (`backend/app/campus.py`, store in `backend/app/campus_store.py`)

```
GET  /api/campus/status                     index stats + store backend
GET  /api/campus/countries                  201 countries with counts
GET  /api/campus/universities?q=&country=   search, paginated (≤100)
GET  /api/campus/universities/{id}          one university + member count
POST /api/campus/register {username, password}
POST /api/campus/login                      -> {token, username}
POST /api/campus/logout  (Bearer)
GET  /api/campus/me       (Bearer)          account + affiliation
POST /api/campus/join {university_id}       one affiliation; re-join switches
POST /api/campus/leave
GET  /api/campus/leaderboard                universities by member count
GET  /api/campus/members?university_id=
```

Auth: usernames `3-32 [a-zA-Z0-9_.-]`, passwords `6+`, pbkdf2-sha256
(200 000 rounds, stdlib), bearer sessions (30 days). No new dependencies
(httpx was already required).

## Persistence

`GET /api/campus/status` reports the active backend (`backend` for
memberships, `experiments_backend` for experiments):

- **shared-kv** — ✅ active in production (`upstash-kv-amethyst-harbor`,
  connected to the `brainlaber` project, env auto-injected). Atomic
  counters/sets; memberships **and Lab experiments** shared across all
  visitors and surviving restarts (keys `nl:exp:*`, atomic `nl:exp:counter`).
- **local-file** — local dev (`data/campus_store.json`, gitignored).
- **ephemeral-tmp** — fallback when no KV is configured (the UI then shows
  a DEMO MODE banner).

## Tests

`tests/test_campus.py`: index integrity, search, password hashing, file-store
join/switch/leave/leaderboard, full HTTP flow + auth guards.
