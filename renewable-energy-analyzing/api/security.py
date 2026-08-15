"""Reusable security building blocks for the API.

Two pieces:

* :class:`SecurityHeadersMiddleware` — sets a strict, self-only Content-Security
  -Policy plus the usual hardening headers on every response. Because the
  dashboard ships its own vendored Chart.js (no CDN) and keeps JS/CSS in
  separate files (no inline), the CSP can stay as tight as ``'self'``.
* :class:`RateLimiter` — a small in-memory fixed-window limiter keyed by client
  IP, so a single client can't hammer the API. No external dependency.

Both are intentionally simple and readable: security you can audit at a glance.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# One strict policy string, assembled once.
#
# script-src stays 'self' — no inline scripts, which is the protection that
# actually matters against XSS. style-src additionally allows 'unsafe-inline'
# because Chart.js sizes its <canvas> via inline styles and the dashboard sets a
# couple of dynamic widths; inline *style* injection is a far lower risk than
# script injection, so this is the standard, accepted trade-off for Chart.js.
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
])

_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Ignored by browsers over plain HTTP (localhost dev); active behind HTTPS.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


class RateLimiter:
    """Fixed-window per-IP limiter. Thread-safe, memory-only, self-expiring."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_key(self, request: Request) -> str:
        # Uvicorn populates request.client; fall back defensively.
        return request.client.host if request.client else "unknown"

    def allow(self, request: Request) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        key = self._client_key(request)
        with self._lock:
            window_start = now - self.window
            recent = [t for t in self._hits[key] if t > window_start]
            if len(recent) >= self.max_requests:
                retry = self.window - (now - recent[0])
                self._hits[key] = recent
                return False, max(0.0, retry)
            recent.append(now)
            self._hits[key] = recent
            # Opportunistic cleanup so the dict can't grow unbounded.
            if len(self._hits) > 4096:
                for k in list(self._hits):
                    if not self._hits[k] or self._hits[k][-1] <= window_start:
                        self._hits.pop(k, None)
            return True, 0.0


def rate_limit_middleware_factory(limiter: RateLimiter):
    """Build an ASGI-style middleware that enforces ``limiter`` on /api routes."""

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path.startswith("/api/"):
                allowed, retry = limiter.allow(request)
                if not allowed:
                    return JSONResponse(
                        {"error": "rate_limited",
                         "detail": "Too many requests, please slow down."},
                        status_code=429,
                        headers={"Retry-After": str(int(retry) + 1)},
                    )
            return await call_next(request)

    return RateLimitMiddleware
