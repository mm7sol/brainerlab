# Security Policy

## Scope

BrainerLab is **currently under development and not publicly live**.
This repository contains scientific code, documentation and curated reference
data. It must never contain secrets, private infrastructure details, user
data, API keys or deployment credentials.

## What must never be committed

- `.env.local` / any `.env*` file with real values (only `.env.example`
  with empty placeholders is tracked)
- Upstash / Vercel KV tokens, Redis URLs, OIDC tokens
- `data/campus_store.json` (local account/session store)
- `data/imports/*.json` (user-uploaded circuits)
- `data/raw/*` (downloaded source datasets, except `.gitkeep`)
- `experiments/NL-EXP-*.json` except the curated reference
  `experiments/NL-EXP-000001.json` (local runs are runtime state)
- `.vercel/project.json` (deployment identifiers)

All of the above are covered by `.gitignore`. If you spot a secret in the
history, open a confidential issue immediately so it can be revoked and
purged.

## Reporting a vulnerability

Please report security issues privately (open a GitHub security advisory or
contact the maintainers directly) rather than filing a public issue. Include:

1. A description of the issue and its potential impact
2. Steps to reproduce (without including any real credentials)
3. Any relevant logs with secrets redacted

We aim to acknowledge reports within 7 days.

## Data handling

- Curated datasets keep their own licences (see `data/registry/datasets.json`).
  Never redistribute a dataset beyond what its licence allows.
- User-uploaded circuits are labelled **unverified** and are never bundled
  with curated reference data.
- The campus account store uses salted `pbkdf2-sha256` password hashes
  (stdlib only); no plaintext passwords are ever stored.
