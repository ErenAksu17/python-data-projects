"""Transport hardening: origins, headers, body size and request rate.

Small service, but it is exposed to the internet, so the basics are not
optional. Everything is configurable through environment variables so the
container can be locked down without a rebuild.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

#: Comma-separated allowlist, e.g. "https://erenaksu17.github.io".
ENV_ORIGINS = "VFACTORY_ALLOWED_ORIGINS"
DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

#: Requests per window per client address.
ENV_RATE_LIMIT = "VFACTORY_RATE_LIMIT"
DEFAULT_RATE_LIMIT = 120
RATE_WINDOW_SECONDS = 60.0

#: Largest request body accepted, in bytes.
ENV_MAX_BODY = "VFACTORY_MAX_BODY_BYTES"
DEFAULT_MAX_BODY = 2 * 1024 * 1024

#: Concurrent WebSocket streams the process will serve.
ENV_MAX_STREAMS = "VFACTORY_MAX_STREAMS"
DEFAULT_MAX_STREAMS = 32


def allowed_origins() -> list[str]:
    raw = os.getenv(ENV_ORIGINS, "").strip()
    if not raw:
        return list(DEFAULT_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


def rate_limit() -> int:
    return _int_env(ENV_RATE_LIMIT, DEFAULT_RATE_LIMIT)


def max_body_bytes() -> int:
    return _int_env(ENV_MAX_BODY, DEFAULT_MAX_BODY)


def max_streams() -> int:
    return _int_env(ENV_MAX_STREAMS, DEFAULT_MAX_STREAMS)


#: JSON endpoints render nothing, so they get the strictest policy there is.
API_CSP = "default-src 'none'; frame-ancestors 'none'"

#: The bundled dashboard needs its own script, style and same-origin fetches --
#: and nothing else. No CDN, no inline script, no third-party anything.
APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def websocket_origin_allowed(origin: str | None) -> bool:
    """Check a WebSocket handshake's Origin against the CORS allowlist.

    Neither ``CORSMiddleware`` nor any HTTP middleware sees a WebSocket
    handshake, and browsers do not apply the same-origin policy to WebSockets
    -- so without this check any page on the internet could open a stream
    against a deployed API. Requests with no Origin header at all (native
    clients, curl, the test client) are allowed: Origin is a browser signal,
    and refusing it would only break non-browser callers while stopping nobody.
    """
    if origin is None:
        return True
    allowed = allowed_origins()
    return "*" in allowed or origin in allowed


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative headers, tightened further on the pure-JSON routes."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        api_route = path.startswith("/api") or path in ("/healthz", "/livez")

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy", API_CSP if api_route else APP_CSP
        )
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies up front instead of buffering them."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        super().__init__(app)
        self._max = max_bytes or max_body_bytes()

    async def dispatch(self, request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self._max:
            return JSONResponse(
                {"detail": "request body too large"}, status_code=413
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-cost sliding window per client address.

    In-process and therefore per-replica: enough to stop a single client from
    hammering a free-tier container, not a substitute for an edge WAF.
    """

    def __init__(self, app: ASGIApp, limit: int | None = None) -> None:
        super().__init__(app)
        self._limit = limit or rate_limit()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/healthz", "/livez"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self._hits[client]
        cutoff = now - RATE_WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._limit:
            retry_after = int(RATE_WINDOW_SECONDS - (now - bucket[0])) + 1
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        # Stop the dict growing without bound on a long-lived process.
        if len(self._hits) > 4_096:
            for key in [k for k, v in self._hits.items() if not v][:1_024]:
                self._hits.pop(key, None)
        return await call_next(request)
