"""Vercel serverless entrypoint — exposes the FastAPI app.

All routes (API + static frontend served by FastAPI) are rewritten here
via vercel.json. Vercel's filesystem is read-only except /tmp: the app
itself handles that (see backend/app/main.py — EXP_DIR overlay).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402  (Vercel looks for `app`)

__all__ = ["app"]
