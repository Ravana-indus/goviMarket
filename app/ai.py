"""Shared Gemini switches: on/off, offline mode for canned demo data, and the last failure."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

log = logging.getLogger("govi.ai")
_offline: ContextVar[bool] = ContextVar("offline", default=False)
last_error: dict = {}
endpoint: dict = {}  # which API the key ended up on, for /admin/diag


_client = None
# Default model. Override with GEMINI_MODEL; /admin/diag shows the exact error if the name is wrong.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def client():
    """One Gemini client for the whole process. A client made inline and dropped gets garbage
    collected mid-call, which closes its connection ("client has been closed")."""
    global _client
    if _client is None:
        _client = _connect(os.environ["GEMINI_API_KEY"])
    return _client


def _connect(key: str):
    """Pick the endpoint the key works on. AI Studio keys (projects named gen-lang-client-...) use
    the Gemini API; Vertex AI express keys only work on Vertex. Both kinds can start with "AQ.",
    so for those try each endpoint once and keep the first that knows MODEL. GEMINI_VERTEX=1/0
    skips the guess. The key already carries its Google Cloud project, so none is passed."""
    from google import genai
    forced = os.getenv("GEMINI_VERTEX")
    if forced in ("0", "1"):
        order = [forced == "1"]
    else:
        order = [False, True] if key.startswith("AQ.") else [False]
    made = [genai.Client(vertexai=True, api_key=key) if v else genai.Client(api_key=key) for v in order]
    if len(made) == 1:
        endpoint.update(name="vertex" if order[0] else "gemini-api")
        return made[0]
    for v, c in zip(order, made):
        try:
            c.models.get(model=MODEL)
            endpoint.update(name="vertex" if v else "gemini-api")
            return c
        except Exception as e:
            failed("connect " + ("vertex" if v else "gemini-api"), e)
    endpoint.update(name="none worked (gemini-api kept)")
    return made[0]


def enabled() -> bool:
    return bool(os.getenv("GEMINI_API_KEY")) and not _offline.get()


@contextmanager
def offline():
    """Use the built-in parser and message templates (demo seed: fast, free, no rate limits)."""
    tok = _offline.set(True)
    try:
        yield
    finally:
        _offline.reset(tok)


def failed(where: str, e: Exception) -> None:
    log.warning("gemini %s failed: %s: %s", where, type(e).__name__, e)
    last_error.update(where=where, error=f"{type(e).__name__}: {e}"[:400],
                      at=datetime.now(timezone.utc).isoformat())
