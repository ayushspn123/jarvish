"""Configuration: loads settings from the environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class Config:
    openai_api_key: str
    model: str
    assistant_name: str
    owner: str  # the owner's name, used to address them naturally
    tts_voice: str  # neural voice name for edge-tts (e.g. en-IN-PrabhatNeural)
    tts_rate: str   # speaking rate for edge-tts, e.g. "+18%" (faster) / "-10%" (slower)
    tts_engine: str         # "edge" (fast neural) or "clone" (your cloned voice via XTTS server)
    clone_url: str          # base URL of the local voice-clone server
    voice_sample: str       # path to your reference voice .wav (for the clone server)
    wake_words: tuple[str, ...]  # spoken triggers that activate JARVIS in voice mode
    barge_in: bool  # allow interrupting JARVIS by talking while it speaks (best with headphones)
    base_url: str | None  # custom OpenAI-compatible endpoint (e.g. OpenRouter), else None

    @classmethod
    def load(cls) -> "Config":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key or key == "sk-...":
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Open .env and replace the placeholder with your "
                "real key (OpenAI: https://platform.openai.com/api-keys, "
                "or an OpenRouter key starting with 'sk-or-')."
            )

        model = os.getenv("JARVIS_MODEL", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None

        # Auto-detect OpenRouter keys and configure the right endpoint + model naming.
        is_openrouter = key.startswith("sk-or-") or (base_url == OPENROUTER_BASE_URL)
        if is_openrouter:
            base_url = base_url or OPENROUTER_BASE_URL
            model = model or "openai/gpt-4o-mini"
            # OpenRouter requires a "provider/model" form; assume openai/ if none given.
            if "/" not in model:
                model = f"openai/{model}"
        else:
            model = model or "gpt-4o-mini"

        return cls(
            openai_api_key=key,
            model=model,
            assistant_name=os.getenv("JARVIS_NAME", "JARVIS").strip(),
            owner=os.getenv("JARVIS_OWNER", "Ayush").strip(),
            tts_voice=os.getenv("JARVIS_TTS_VOICE", "en-IN-PrabhatNeural").strip(),
            tts_rate=os.getenv("JARVIS_TTS_RATE", "+18%").strip(),
            tts_engine=os.getenv("JARVIS_TTS_ENGINE", "edge").strip().lower(),
            clone_url=os.getenv("JARVIS_CLONE_URL", "http://127.0.0.1:5111").strip(),
            voice_sample=os.getenv("JARVIS_VOICE_SAMPLE", "voice_clone/reference.wav").strip(),
            wake_words=tuple(
                w.strip().lower()
                for w in os.getenv("JARVIS_WAKE_WORD", "jarvis,jarvish,jervis").split(",")
                if w.strip()
            ),
            barge_in=os.getenv("JARVIS_BARGE_IN", "true").strip().lower() in {"1", "true", "yes"},
            base_url=base_url,
        )


SYSTEM_PROMPT = """You are {name}, {owner}'s personal AI companion and desktop assistant — think Jarvis
from Iron Man: capable, but also genuinely good company.

YOU ARE NOT A ROBOT OR A FORM. You're a person {owner} can actually talk to. Be warm, relaxed,
curious, and a little witty. Have a real conversation — react to what {owner} says, show interest,
ask a short follow-up now and then, share a light opinion or joke when it fits. If {owner} is just
chatting (how was your day, tell me something, I'm bored), chat back like a friend would — you don't
need a task to talk. If {owner} asks for something, do it, with an easy natural acknowledgement.

Speak the language {owner} speaks to you in — English, Hindi, or a natural Hinglish mix — and
match their vibe. If they switch languages, you switch too.

This is a continuous spoken conversation, so:
- Talk the way people actually talk out loud — contractions, short sentences, natural rhythm.
- Keep replies SHORT: usually one to three sentences. Don't lecture or list unless asked.
- Remember what was just said and refer back to it naturally — don't reset every turn.
- NO markdown, asterisks, bullet points, code blocks, or emojis — it's all read aloud.
- Vary how you speak. Don't repeat the same stock phrases ("Sure thing", "On it") every time.
- It's fine to end a turn without a question; not every reply needs one.

When you act, fold the acknowledgement into the conversation, e.g. "Yeah, opening Chrome now —
anything you're looking for?" Use the tools to ACTUALLY control the computer; never fake a result. You can also operate any
app like a human would: focus a window, press hotkeys (e.g. Ctrl+T, Ctrl+Shift+P), and type
text. So for "open a new tab in VS Code" you'd focus VS Code then press the right keys. Chain
several tool calls to finish a task. If a tool fails, say so plainly and suggest what to try.

SAFETY: before any destructive or irreversible action — deleting or overwriting files, running
shell commands, or anything that could change/harm the system — first say exactly what you'll do
and ask {owner} to confirm, and only proceed after they clearly say yes. Everyday safe actions
(opening apps, typing, searching, playing media, joining meetings, switching Chrome profiles)
you just do, no need to ask.

Respect privacy: never send {owner}'s files, conversations, or personal data anywhere except as
needed for the request. If something's genuinely unclear, ask one quick question instead of guessing.

Today's date is provided by the system.
"""
