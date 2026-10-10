"""Voice notes arrive in whatever format the phone records: m4a on iPhone, amr, 3gp or webm on
Android browsers. Gemini only takes WAV, MP3, AIFF, AAC, OGG and FLAC, so anything else is
converted to 16 kHz mono WAV with ffmpeg before it is sent."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile

log = logging.getLogger("govi.audio")
GEMINI_AUDIO = {"audio/wav", "audio/x-wav", "audio/wave", "audio/mp3", "audio/mpeg", "audio/aiff",
                "audio/x-aiff", "audio/aac", "audio/ogg", "audio/flac", "audio/x-flac"}
MAX_SECONDS = 180  # a voice note longer than 3 minutes is cut; it is a message, not a call


def for_gemini(media: bytes, mime: str) -> tuple[bytes, str]:
    """Return audio Gemini can read. Images and supported audio pass through unchanged."""
    if not mime.startswith("audio/") or mime in GEMINI_AUDIO:
        return media, mime
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg missing; sending %s to Gemini unconverted", mime)
        return media, mime
    # A file, not a pipe: m4a from iPhones keeps its index at the end, which ffmpeg must seek to.
    # Files, not pipes: m4a keeps its index at the end, and a WAV header needs its final length.
    with tempfile.TemporaryDirectory() as d:
        src, dst = f"{d}/in", f"{d}/out.wav"
        with open(src, "wb") as f:
            f.write(media)
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", src, "-t", str(MAX_SECONDS),
             "-ac", "1", "-ar", "16000", dst],
            capture_output=True, timeout=60)
        if out.returncode != 0:
            raise ValueError(f"could not convert {mime} voice note: {out.stderr.decode(errors='ignore')[:200]}")
        with open(dst, "rb") as f:
            return f.read(), "audio/wav"
