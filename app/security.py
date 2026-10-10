"""Access control, rate limits and safe headers.

- Ops console and its APIs need ADMIN_TOKEN (cookie after /login, or the X-Admin-Token header
  for Cloud Scheduler jobs), or a phone sign-in from a number in ADMIN_PHONES.
- Market agents need AGENT_PIN (X-Agent-Pin header) to post prices, or a phone sign-in whose
  profile role is agent (they gave the PIN once when they took that role).
- With a variable unset, that gate is open; /healthz reports it so nobody deploys open by accident.
- Public writes (intake, orders, listings, agent prices, login) are rate limited per IP."""
from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE = "govi_admin"
ADMIN_PREFIXES = ("/admin", "/state", "/demo/", "/shipments/", "/surplus/", "/api/offers", "/api/plan", "/api/swaps", "/jobs/")
ADMIN_EXACT = {("POST", "/plan")}
LIMITED = {"/intake", "/api/orders", "/api/listings", "/api/agent/prices", "/login",
           "/api/auth/start", "/api/auth/verify"}
RATE = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
_hits: dict[str, deque] = defaultdict(deque)


def admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "")


def agent_pin() -> str:
    return os.getenv("AGENT_PIN", "")


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode(), (b or "").encode())


def _account(request: Request) -> dict | None:
    from . import accounts
    return accounts.current(request)


def is_admin(request: Request) -> bool:
    tok = admin_token()
    if not tok:
        return True
    if _same(request.cookies.get(COOKIE, ""), tok) or _same(request.headers.get("x-admin-token", ""), tok):
        return True
    from . import accounts
    u = _account(request)
    return bool(u) and u["phone"] in accounts.admin_phones()


def is_agent(request: Request) -> bool:
    pin = agent_pin()
    if not pin or _same(request.headers.get("x-agent-pin", ""), pin) or is_admin(request) and bool(admin_token()):
        return True
    u = _account(request)
    return bool(u) and u.get("role") == "agent"


def _needs_admin(request: Request) -> bool:
    p, m = request.url.path, request.method
    if (m, p) in ADMIN_EXACT:
        return True
    if p.startswith("/api/agent/reports/"):  # approve / reject a flagged price
        return True
    if p == "/api/agent/reports" and "phone" not in request.query_params:
        return True
    return p.startswith(ADMIN_PREFIXES)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def _limited(request: Request) -> bool:
    if request.method != "POST" or request.url.path not in LIMITED:
        return False
    key = f"{_client_ip(request)}:{request.url.path}"
    q, now = _hits[key], time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE:
        return True
    q.append(now)
    return False


async def middleware(request: Request, call_next):
    if _limited(request):
        return JSONResponse({"detail": "Too many requests. Please wait a minute and try again."}, status_code=429)
    if _needs_admin(request) and not is_admin(request):
        if request.method == "GET" and request.url.path == "/admin":
            return RedirectResponse("/login?next=/admin", status_code=303)
        return JSONResponse({"detail": "Sign in to the console first."}, status_code=401)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


def reset_limits() -> None:
    _hits.clear()
