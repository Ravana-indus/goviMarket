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


_client = None
# gemini-2.5-flash was retired for new API keys in Oct 2026 (404 NOT_FOUND). One place to change it.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def client():
    """One Gemini client for the whole process. A client made inline and dropped gets garbage
    collected mid-call, which closes its connection ("client has been closed")."""
    global _client
    if _client is None:
        from google import genai
        key = os.environ["GEMINI_API_KEY"]
        # Keys starting "AQ." are Vertex AI express-mode keys; they only work on the Vertex endpoint.
        # "AIza..." keys from AI Studio use the Gemini API. GEMINI_VERTEX=1/0 overrides the guess.
        vertex = os.getenv("GEMINI_VERTEX", "1" if key.startswith("AQ.") else "0") == "1"
        _client = genai.Client(vertexai=True, api_key=key) if vertex else genai.Client(api_key=key)
    return _client


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
