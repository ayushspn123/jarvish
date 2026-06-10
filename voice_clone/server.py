"""XTTS-v2 voice-cloning synthesis server.

Runs in the Python 3.11 `.venv-clone` environment (Coqui XTTS doesn't support 3.13). Loads the
model and your reference voice ONCE, then serves fast-ish synthesis over a tiny local HTTP API
so the main JARVIS app (Python 3.13) can speak in your cloned voice without reloading the model.

Start it:
    .venv-clone\\Scripts\\python.exe voice_clone\\server.py --reference voice_clone\\reference.wav

API:
    GET  /health           -> {"status": "ready"}  once the model + voice are loaded
    POST /tts  {"text": ?}  -> audio/wav bytes (24 kHz mono)
"""

from __future__ import annotations

import argparse
import io
import os

# Auto-accept the Coqui Public Model License so the model download doesn't block on a prompt.
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import soundfile as sf  # noqa: E402
from flask import Flask, Response, jsonify, request  # noqa: E402

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

app = Flask(__name__)

# Populated by _load_model() at startup.
_model = None
_gpt_cond_latent = None
_speaker_embedding = None
_sample_rate = 24000
_language = "en"


def _load_model(reference_wav: str) -> None:
    """Load XTTS-v2 and precompute the speaker latents from the reference clip (once)."""
    global _model, _gpt_cond_latent, _speaker_embedding, _sample_rate
    from TTS.api import TTS

    print("Loading XTTS-v2 (first run downloads ~1.8 GB)...", flush=True)
    tts = TTS(MODEL_NAME, progress_bar=False)
    _model = tts.synthesizer.tts_model
    _sample_rate = tts.synthesizer.output_sample_rate or 24000

    print(f"Computing voice fingerprint from {reference_wav} ...", flush=True)
    _gpt_cond_latent, _speaker_embedding = _model.get_conditioning_latents(
        audio_path=[reference_wav]
    )
    print("Voice ready. Server is live.", flush=True)


@app.get("/health")
def health() -> Response:
    ready = _model is not None and _speaker_embedding is not None
    return jsonify({"status": "ready" if ready else "loading"})


@app.post("/tts")
def tts() -> Response:
    if _model is None:
        return jsonify({"error": "model not loaded"}), 503
    text = (request.get_json(force=True, silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "no text"}), 400

    out = _model.inference(
        text,
        _language,
        _gpt_cond_latent,
        _speaker_embedding,
        temperature=0.7,
    )
    buf = io.BytesIO()
    sf.write(buf, out["wav"], _sample_rate, format="WAV")
    buf.seek(0)
    return Response(buf.read(), mimetype="audio/wav")


def main() -> None:
    parser = argparse.ArgumentParser(description="XTTS-v2 voice cloning server")
    parser.add_argument("--reference", required=True, help="Path to your reference voice .wav")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5111)
    args = parser.parse_args()

    if not os.path.isfile(args.reference):
        raise SystemExit(
            f"Reference voice not found: {args.reference}\n"
            "Record one first:  .venv\\Scripts\\python.exe record_sample.py"
        )

    _load_model(args.reference)
    # threaded=False: XTTS inference isn't thread-safe; serve requests one at a time.
    app.run(host=args.host, port=args.port, threaded=False)


if __name__ == "__main__":
    main()
