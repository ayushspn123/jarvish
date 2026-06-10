# JARVIS 🤖

A Jarvis-style desktop assistant for Windows, powered by an LLM tool-calling loop.

JARVIS uses the OpenAI API as its "brain": you make a request in plain language, the model
reasons about it, and it calls real Python tools to control your computer, manage files,
search the web, and more. Works in **text** mode or hands-free **voice** mode.

## Features (MVP)

- **Text chat + tool loop** — the core reasoning engine that decides which tools to use.
- **System & file control** — open/close apps, run commands, find/create/move/copy/zip files.
- **Web search & summarize** — search DuckDuckGo and read/summarize any page.
- **Voice mode** — speak to JARVIS and hear it reply (`--voice`).
- **Safety first** — destructive actions (delete, run command, close app) require your
  explicit confirmation before they run.

## Setup

```powershell
# 1. (Recommended) create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
copy .env.example .env
notepad .env        # paste your OPENAI_API_KEY
```

> **Voice mode** needs a microphone and `PyAudio`. If `pip install PyAudio` fails on Windows,
> try: `pip install pipwin && pipwin install pyaudio`. Text mode works without it.

## Run

```powershell
# Text mode
python -m jarvis

# Voice mode (microphone + speaker)
python -m jarvis --voice
```

Then just ask, e.g.:

- "Open VS Code."
- "Create a folder called AI Projects on my Desktop."
- "Find all PDFs in my Downloads."
- "Search the web for the latest MERN job trends and summarize."
- "What's my system status?"

## How it works

```
You ──▶ Jarvis.chat() ──▶ OpenAI model
                              │
                  wants a tool? ──yes──▶ registry.call_tool() ──▶ result ──┐
                              │                                            │
                              no                          (fed back to the model)
                              ▼                                            │
                        final reply ◀──────────────────────────────────────┘
```

Tools live in [jarvis/tools/](jarvis/tools/). Each is a plain function decorated with
`@tool(...)`, which auto-registers its OpenAI schema. **Adding a capability = writing one
decorated function** — the brain picks it up automatically.

```python
from .registry import tool

@tool(
    name="play_music",
    description="Play a song or playlist.",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
)
def play_music(query: str) -> str:
    ...
    return "Now playing."
```

Mark a tool `confirm=True` to require the owner's approval before it runs.

## Project layout

| Path | Purpose |
|------|---------|
| [jarvis/brain.py](jarvis/brain.py) | OpenAI tool-calling loop |
| [jarvis/config.py](jarvis/config.py) | settings + system prompt |
| [jarvis/voice.py](jarvis/voice.py) | speech-to-text + text-to-speech |
| [jarvis/tools/registry.py](jarvis/tools/registry.py) | `@tool` decorator + dispatcher |
| [jarvis/tools/system.py](jarvis/tools/system.py) | apps, commands, system status |
| [jarvis/tools/files.py](jarvis/tools/files.py) | file operations |
| [jarvis/tools/web.py](jarvis/tools/web.py) | web search + page fetch |
| [jarvis/main.py](jarvis/main.py) | CLI entry point (text & voice) |

## Roadmap ideas

Vision/OCR (screenshots), browser automation, email, reminders/calendar, long-term memory,
and a local-model option are natural next steps — each is just another tool module.

## Privacy

JARVIS runs locally. It never uploads your files or conversations anywhere except to the
OpenAI API to fulfill your request. There is no hidden logging or data exfiltration.
