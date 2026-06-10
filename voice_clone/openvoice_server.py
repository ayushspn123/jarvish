"""OpenVoice v2 voice-cloning synthesis server (fast local clone).

Pipeline:  MeloTTS speaks the text in a base voice  ->  OpenVoice's tone-color converter
reshapes that audio's timbre to match YOUR reference voice. MeloTTS is fast on CPU and the
converter is light, so this is usable for conversation (a few seconds per reply) — unlike XTTS.

Runs in the Python 3.11 `.venv-clone` environment. Loads everything ONCE, then serves a tiny
local HTTP API so the main JARVIS app (Python 3.13) can speak in your cloned voice.

Start it:
    .venv-clone\\Scripts\\python.exe voice_clone\\openvoice_server.py --reference voice_clone\\reference.wav

API:
    GET  /health           -> {"status": "ready"} once loaded
    POST /tts  {"text": ?}  -> audio/wav bytes
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile

import soundfile as sf
import torch
from flask import Flask, Response, jsonify, request

# Use all physical cores for CPU inference.
try:
    torch.set_num_threads(max(1, (os.cpu_count() or 2)))
except Exception:  # noqa: BLE001
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
# The OpenVoice repo is vendored here (not pip-installed); add it to the import path.
sys.path.insert(0, os.path.join(_HERE, "OpenVoice"))

CKPT_DIR = os.path.join(_HERE, "checkpoints_v2")

app = Flask(__name__)

# Populated at startup.
_melo = None
_speaker_id = None
_converter = None
_source_se = None
_target_se = None
_sample_rate = 22050
_speed = 1.15  # MeloTTS speaking rate; >1 is faster (also slightly quicker to synthesize)


def _pick_speaker(spk2id: dict, requested: str) -> str:
    """Choose a MeloTTS speaker key. Prefer the requested one, then an Indian-accent voice."""
    keys = list(spk2id.keys())
    if requested in spk2id:
        return requested
    for k in keys:
        if "INDIA" in k.upper():
            return k
    return keys[0]


def _se_path_for(speaker_key: str) -> str:
    """Map a MeloTTS speaker key (e.g. 'EN_INDIA') to its base-speaker SE file."""
    norm = speaker_key.lower().replace("_", "-").replace(" ", "-")
    path = os.path.join(CKPT_DIR, "base_speakers", "ses", f"{norm}.pth")
    if not os.path.isfile(path):
        path = os.path.join(CKPT_DIR, "base_speakers", "ses", "en-default.pth")
    return path


def _load(reference_wav: str, base_speaker: str) -> None:
    global _melo, _speaker_id, _converter, _source_se, _target_se, _sample_rate
    from melo.api import TTS as MeloTTS
    from openvoice.api import ToneColorConverter

    print("Loading tone-color converter...", flush=True)
    _converter = ToneColorConverter(
        os.path.join(CKPT_DIR, "converter", "config.json"),
        device="cpu",
    )
    _converter.load_ckpt(os.path.join(CKPT_DIR, "converter", "checkpoint.pth"))
    # No watermark model needed (and it avoids the extra `wavmark` dependency).
    _converter.watermark_model = None
    _sample_rate = _converter.hps.data.sampling_rate

    print("Loading MeloTTS base voice...", flush=True)
    _melo = MeloTTS(language="EN", device="cpu")
    spk2id = _melo.hps.data.spk2id
    speaker_key = _pick_speaker(spk2id, base_speaker)
    _speaker_id = spk2id[speaker_key]
    print(f"Base speaker: {speaker_key}", flush=True)

    _source_se = torch.load(_se_path_for(speaker_key), map_location="cpu")

    print(f"Fingerprinting your voice from {reference_wav} ...", flush=True)
    _target_se = _converter.extract_se([reference_wav])

    # Warm up the models so the FIRST real reply isn't slow (JIT/caches).
    print("Warming up...", flush=True)
    try:
        _synth("Warming up.")
    except Exception as exc:  # noqa: BLE001
        print(f"(warmup skipped: {exc})", flush=True)
    print("Voice ready. Server is live.", flush=True)


def _synth(text: str):
    """Generate base speech then reshape it into the cloned voice. Returns (audio, sample_rate)."""
    base_path = tempfile.mktemp(suffix=".wav")
    try:
        _melo.tts_to_file(text, _speaker_id, base_path, speed=_speed)
        audio = _converter.convert(
            audio_src_path=base_path,
            src_se=_source_se,
            tgt_se=_target_se,
            tau=0.3,
            message="@JARVIS",
        )
        return audio
    finally:
        try:
            os.remove(base_path)
        except OSError:
            pass


@app.get("/health")
def health() -> Response:
    ready = _converter is not None and _target_se is not None
    return jsonify({"status": "ready" if ready else "loading"})


@app.post("/tts")
def tts() -> Response:
    if _converter is None:
        return jsonify({"error": "model not loaded"}), 503
    text = (request.get_json(force=True, silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "no text"}), 400

    audio = _synth(text)
    buf = io.BytesIO()
    sf.write(buf, audio, _sample_rate, format="WAV")
    buf.seek(0)
    return Response(buf.read(), mimetype="audio/wav")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenVoice v2 voice cloning server")
    parser.add_argument("--reference", required=True, help="Path to your reference voice .wav")
    parser.add_argument("--base-speaker", default="EN_INDIA", help="MeloTTS base speaker key")
    parser.add_argument("--speed", type=float, default=1.15, help="Speaking rate (>1 faster)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5111)
    args = parser.parse_args()

    global _speed
    _speed = args.speed

    if not os.path.isfile(args.reference):
        raise SystemExit(
            f"Reference voice not found: {args.reference}\n"
            "Record one first:  .venv\\Scripts\\python.exe record_sample.py"
        )

    _load(args.reference, args.base_speaker)
    app.run(host=args.host, port=args.port, threaded=False)


if __name__ == "__main__":
    main()
