"""JARVIS web app backend.

Serves a browser UI (with WebRTC echo-cancelled mic + barge-in) and bridges it to the existing
Python brain + tools over a WebSocket. The browser does speech recognition; this server runs the
brain and returns the reply text plus neural-voice audio (edge-tts) to play.

Run:
    .venv\\Scripts\\python.exe -m webapp.server
Then open http://localhost:8000  (or http://<your-laptop-ip>:8000 on your phone, same WiFi).
"""

from __future__ import annotations

import asyncio
import base64
import os
import random

import edge_tts
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from jarvis import tools
from jarvis.brain import Jarvis
from jarvis.config import Config

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC = os.path.join(_HERE, "static")

cfg = Config.load()
# Full control: tool actions run. Safety comes from the brain confirming destructive/irreversible
# actions in conversation first (see SYSTEM_PROMPT) before it ever calls them.
tools.registry.confirm_callback = lambda _action: True

# Short spoken acknowledgements so you're not met with silence while the brain works.
FILLERS = [
    "Haan, ek second...",
    "Let me check that.",
    "One moment...",
    "Dekh raha hoon...",
    "On it, just a sec.",
    "Theek hai, dekhta hoon.",
]

app = FastAPI(title="JARVIS")


async def _tts_b64(text: str) -> str:
    """Synthesize `text` with the neural voice and return base64-encoded mp3."""
    communicate = edge_tts.Communicate(text, cfg.tts_voice, rate=cfg.tts_rate)
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return base64.b64encode(bytes(audio)).decode("ascii")


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    jarvis = Jarvis(cfg)
    loop = asyncio.get_event_loop()
    await websocket.send_json({"type": "ready", "name": cfg.assistant_name, "owner": cfg.owner})
    try:
        while True:
            data = await websocket.receive_json()
            kind = data.get("type")
            if kind == "reset":
                jarvis.reset()
                continue
            if kind != "message":
                continue
            text = (data.get("text") or "").strip()
            if not text:
                continue

            # Immediate spoken filler so there's no dead silence while the brain thinks.
            filler = random.choice(FILLERS)
            await websocket.send_json({"type": "filler", "text": filler})
            try:
                await websocket.send_json({"type": "audio", "b64": await _tts_b64(filler)})
            except Exception:  # noqa: BLE001
                pass

            # The brain is synchronous (OpenAI client + tools) — run it off the event loop.
            reply = await loop.run_in_executor(None, jarvis.chat, text)
            await websocket.send_json({"type": "reply", "text": reply})
            try:
                await websocket.send_json({"type": "audio", "b64": await _tts_b64(reply)})
            except Exception:  # noqa: BLE001 — audio is best-effort; text already sent
                pass
    except WebSocketDisconnect:
        return


# Serve the PWA frontend at "/" (defined last so /ws takes precedence).
app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")


def main() -> None:
    import uvicorn

    port = int(os.getenv("JARVIS_WEB_PORT", "8000"))
    kwargs = {"host": "0.0.0.0", "port": port}
    scheme = "http"
    # HTTPS is OPT-IN (JARVIS_WEB_HTTPS=1). Default is plain HTTP, which avoids the Windows
    # asyncio-SSL WebSocket bug (WinError 121). For phone access, use a Cloudflare tunnel
    # (run-mobile.bat) — it provides real HTTPS in front of this HTTP server.
    if os.getenv("JARVIS_WEB_HTTPS") == "1":
        cert, key = os.path.join(_HERE, "cert.pem"), os.path.join(_HERE, "key.pem")
        if os.path.isfile(cert) and os.path.isfile(key):
            kwargs["ssl_certfile"] = cert
            kwargs["ssl_keyfile"] = key
            scheme = "https"
    print(f"JARVIS web app on {scheme}://localhost:{port}")
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    main()
