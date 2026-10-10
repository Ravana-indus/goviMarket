import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app import audio, parser

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _tone(tmp_path, ext, codec):
    out = tmp_path / f"voice.{ext}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", codec, str(out)], check=True)
    return out.read_bytes()


def test_supported_audio_and_images_pass_through():
    assert audio.for_gemini(b"x", "audio/ogg") == (b"x", "audio/ogg")
    assert audio.for_gemini(b"x", "image/jpeg") == (b"x", "image/jpeg")


@needs_ffmpeg
@pytest.mark.parametrize("ext,codec,mime", [("m4a", "aac", "audio/mp4"), ("m4a", "aac", "audio/x-m4a"),
                                            ("webm", "libopus", "audio/webm"), ("3gp", "aac", "audio/3gpp")])
def test_phone_recordings_become_wav(tmp_path, ext, codec, mime):
    data, out_mime = audio.for_gemini(_tone(tmp_path, ext, codec), mime)
    assert out_mime == "audio/wav" and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


@needs_ffmpeg
def test_parser_sends_wav_to_gemini(tmp_path):
    seen = {}

    def generate_content(model, contents, config):
        seen["mime"] = contents[0].inline_data.mime_type
        return SimpleNamespace(text=('{"role":"farmer","language":"si","sender_name":null,"location":"Dambulla","when":null,'
                                      '"items":[],"unclear":[],"confidence":0.9,"summary_in_sender_language":"ok"}'))

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    parser.parse(media=_tone(tmp_path, "m4a", "aac"), mime_type="audio/mp4", today="2026-10-10", client=client)
    assert seen["mime"] == "audio/wav"


@needs_ffmpeg
def test_garbage_audio_raises_clear_error():
    with pytest.raises(ValueError, match="could not convert"):
        audio.for_gemini(b"not audio at all", "audio/amr")
