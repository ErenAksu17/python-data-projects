"""Hardened read-only API + static dashboard host.

Design decisions that matter for security:

* **Read-only, no user data.** The API only serves a pre-computed JSON artifact.
  There is no database, no write path, no auth surface to get wrong.
* **Every input is validated against an allow-list** (country codes, numeric
  bounds) via FastAPI/Pydantic, so a crafted path or query can't reach unchecked
  code. Unknown countries get a generic 404 — no reflection of the raw input.
* **Strict security headers + tight CSP** on every response (see security.py).
* **CORS locked to localhost.** The dashboard is same-origin; cross-site callers
  are refused rather than allowed with ``*``.
* **Per-IP rate limiting** on /api routes.
* **Generic error responses.** An unexpected exception returns a plain 500 with
  no stack trace or internal detail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as PathParam, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

# Make the pipeline package + this api dir importable, regardless of the cwd
# uvicorn is launched from. Reuse the pipeline config as the single source.
ROOT = Path(__file__).resolve().parents[1]
API_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(API_DIR))
from renewable import config  # noqa: E402

WEB_DIR = ROOT / "web"
ALLOWED_GEOS = set(config.GEO_NAMES.keys())

app = FastAPI(
    title="Renewable Energy Analyzer API",
    version="1.0.0",
    description="Read-only API over Eurostat renewable-energy shares.",
)

# ---- Middleware (order: CORS -> security headers -> rate limit) ------------ #
from security import (  # noqa: E402
    RateLimiter,
    SecurityHeadersMiddleware,
    rate_limit_middleware_factory,
)

_max_req = int(config.get_env("RATE_LIMIT_MAX", "120") or "120")
_window = float(config.get_env("RATE_LIMIT_WINDOW", "60") or "60")
_limiter = RateLimiter(max_requests=_max_req, window_seconds=_window)

app.add_middleware(rate_limit_middleware_factory(_limiter))
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000", "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---- Data loading (once, at import/startup) -------------------------------- #
_DATA: dict = {}
_COUNTRY_INDEX: dict[str, dict] = {}


def load_data(path: Path = config.PROCESSED_JSON) -> None:
    global _DATA, _COUNTRY_INDEX
    if not path.exists():
        raise RuntimeError(
            f"Processed data not found at {path}. "
            f"Run: python scripts/build_data.py"
        )
    _DATA = json.loads(path.read_text(encoding="utf-8"))
    _COUNTRY_INDEX = {c["geo"]: c for c in _DATA.get("countries", [])}


# Load once at import so both uvicorn and TestClient see data without relying on
# lifecycle hooks. Missing data is tolerated here; endpoints surface it clearly.
try:
    load_data()
except Exception:
    pass


# ---- Error handling: never leak internals ---------------------------------- #
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"error": "internal_error"}, status_code=500)


# ---- API routes ------------------------------------------------------------ #
@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "countries": len(_COUNTRY_INDEX)}


@app.get("/api/summary")
def summary() -> dict:
    """Headline payload: EU status, target, trend, sectors, forecast, insights."""
    return {
        "meta": _DATA["meta"],
        "target": _DATA["target"],
        "eu": _DATA["eu"],
        "insights": _DATA["insights"],
    }


@app.get("/api/ranking")
def ranking(limit: int = Query(default=37, ge=1, le=50)) -> dict:
    """Country ranking at the reference year, optionally truncated to ``limit``."""
    rows = _DATA.get("ranking", [])
    return {"reference_year": _DATA["meta"]["reference_year"], "ranking": rows[:limit]}


@app.get("/api/country/{geo}")
def country(
    geo: str = PathParam(..., min_length=2, max_length=10, pattern=r"^[A-Z0-9_]+$"),
) -> dict:
    """Full trend + metrics for one country. ``geo`` must be a known code."""
    if geo not in ALLOWED_GEOS:
        raise HTTPException(status_code=404, detail="Unknown country code")
    item = _COUNTRY_INDEX.get(geo)
    if item is None:
        raise HTTPException(status_code=404, detail="No data for country")
    return item


@app.get("/api/sectors")
def sectors() -> dict:
    return {"year_note": "each sector at its own latest year",
            "sectors": _DATA["eu"]["sectors"]}


@app.get("/api/forecast")
def forecast() -> dict:
    return _DATA["eu"]["forecast"]


# ---- Static dashboard (mounted last so /api and /healthz win) -------------- #
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
