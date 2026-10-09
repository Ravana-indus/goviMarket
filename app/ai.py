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
