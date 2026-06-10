"""JARVIS entry point.

Usage:
    python -m jarvis            # text chat in the terminal
    python -m jarvis --voice    # talk to JARVIS with your microphone
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from rich.console import Console
from rich.prompt import Confirm

from . import tools
from .brain import Jarvis
from .config import Config

console = Console()

# Project root (one level above the `jarvis` package) — used to locate the clone server/venv.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "go", "ahead", "do", "confirm", "please", "fine"}
_NO_WORDS = {"no", "nope", "nah", "cancel", "stop", "don't", "dont", "never", "abort"}


def _make_confirm(speak=None):
    """Build the typed confirmation callback used by destructive tools (text mode)."""

    def confirm(action: str) -> bool:
        console.print(f"[yellow]⚠ JARVIS wants to run:[/yellow] [bold]{action}[/bold]")
        if speak:
            speak("This action needs your confirmation.")
        try:
            return Confirm.ask("[yellow]Allow this?[/yellow]", default=False)
        except (EOFError, KeyboardInterrupt):
            return False

    return confirm


def _make_voice_confirm(voice):
    """Build a spoken yes/no confirmation callback for voice mode."""

    def confirm(action: str) -> bool:
        console.print(f"[yellow]⚠ JARVIS wants to run:[/yellow] [bold]{action}[/bold]")
        for _ in range(2):
            voice.speak("Should I go ahead?")
            console.print("[dim]🎤 (say yes or no)[/dim]")
            words = set(voice.listen().lower().replace("'", "").split())
            if words & _NO_WORDS:
                return False
            if words & _YES_WORDS:
                return True
            voice.speak("Sorry, was that a yes or a no?")
        # Couldn't get a clear answer — default to the safe choice.
        voice.speak("I didn't catch a clear answer, so I'll leave it for now.")
        return False

    return confirm


def _on_tool(name: str, args: dict) -> None:
    console.print(f"[dim]→ using tool [cyan]{name}[/cyan] {args}[/dim]")


def run_text(jarvis: Jarvis) -> None:
    console.print(
        f"[bold green]{jarvis.config.assistant_name}[/bold green] online. "
        "Type your request, or 'exit' to quit.\n"
    )
    while True:
        try:
            user = console.input("[bold cyan]You ›[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            return
        if user.lower() in {"exit", "quit", "bye"}:
            console.print("Goodbye.")
            return
        if not user:
            continue
        with console.status("[dim]thinking...[/dim]"):
            reply = jarvis.chat(user)
        console.print(f"[bold green]{jarvis.config.assistant_name} ›[/bold green] {reply}\n")


# These end the program entirely.
_EXIT_PHRASES = {"exit", "quit", "shut down", "shutdown", "power off", "turn off"}
# These just end the current back-and-forth and go back to waiting for the wake word.
_SLEEP_PHRASES = {
    "go to sleep", "stop listening", "that's all", "thats all", "nothing else",
    "never mind", "nevermind", "goodbye", "bye", "see you", "we're done", "were done",
}
# These wipe the conversation and start fresh (without going to sleep).
_NEW_CHAT_PHRASES = {
    "new chat", "start over", "start fresh", "reset", "forget that", "forget everything",
    "let's start over", "lets start over", "new conversation", "clear",
}
_GOODBYE = "Goodbye."


def _is_new_chat(text: str) -> bool:
    return text.lower().strip(".!? ") in _NEW_CHAT_PHRASES


def _is_exit(text: str) -> bool:
    return text.lower().strip(".!? ") in _EXIT_PHRASES


def _is_sleep(text: str) -> bool:
    return text.lower().strip(".!? ") in _SLEEP_PHRASES


def _token_is_wake(token: str, wake_words) -> bool:
    """True if a single spoken word matches a wake word — exactly, as a fragment, or fuzzily.

    Speech recognition often truncates "jarvis" to "jar"/"jarv" or mishears it, so we're lenient.
    """
    import difflib

    for w in wake_words:
        short, long = sorted((token, w), key=len)
        if len(short) >= 3 and long.startswith(short):
            return True
        if difflib.SequenceMatcher(None, token, w).ratio() >= 0.6:
            return True
    return False


def _strip_wake_word(heard: str, wake_words) -> tuple[bool, str]:
    """If `heard` looks like it starts with a wake word, return (True, the command after it).

    The command may be empty (user said just "Hey JARVIS" and will speak next).
    """
    low = heard.lower()

    # 1) Exact substring match (longest first so "jarvish" beats its prefix "jarvis").
    for w in sorted(wake_words, key=len, reverse=True):
        idx = low.find(w)
        if idx != -1:
            command = heard[idx + len(w):].strip(" ,.!?-")
            return (True, "" if len(command) < 2 else command)

    # 2) Per-word match (handles truncated/misheard wake words).
    words = low.replace(",", " ").replace(".", " ").split()
    for i, token in enumerate(words):
        if _token_is_wake(token, wake_words):
            command = " ".join(words[i + 1:]).strip(" ,.!?-")
            return (True, "" if len(command) < 2 else command)
    return False, ""


def _clone_server_ready(url: str) -> bool:
    import requests

    try:
        r = requests.get(f"{url.rstrip('/')}/health", timeout=2)
        return r.ok and r.json().get("status") == "ready"
    except Exception:  # noqa: BLE001
        return False


def _ensure_clone_server(cfg: Config) -> None:
    """Make sure the local XTTS voice-clone server is running and loaded. Starts it if needed."""
    if _clone_server_ready(cfg.clone_url):
        return

    sample = cfg.voice_sample if os.path.isabs(cfg.voice_sample) else os.path.join(_ROOT, cfg.voice_sample)
    if not os.path.isfile(sample):
        console.print(f"[red]No voice sample found at {sample}.[/red]")
        console.print(
            "Record one first:  [bold].venv\\Scripts\\python.exe record_sample.py[/bold]"
        )
        sys.exit(1)

    clone_python = os.path.join(_ROOT, ".venv-clone", "Scripts", "python.exe")
    server_py = os.path.join(_ROOT, "voice_clone", "openvoice_server.py")
    if not os.path.isfile(clone_python):
        console.print(f"[red]Clone environment missing:[/red] {clone_python}")
        sys.exit(1)

    console.print("[dim]Starting your cloned-voice engine (first run loads the model, ~30s)...[/dim]")
    # Detached so it keeps running; its logs go to a file we can check if something breaks.
    log = open(os.path.join(_ROOT, "voice_clone", "server.log"), "w")
    subprocess.Popen(
        [clone_python, server_py, "--reference", sample],
        cwd=_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
    )

    # Wait (generously) for the model to load and the server to report ready.
    for _ in range(120):  # up to ~4 minutes on first download
        if _clone_server_ready(cfg.clone_url):
            console.print("[green]Cloned voice ready.[/green]")
            return
        time.sleep(2)
    console.print("[yellow]Clone server didn't come up in time; check voice_clone/server.log.[/yellow]")
    console.print("[yellow]Falling back to the neural voice for now.[/yellow]")


def run_voice(jarvis: Jarvis) -> None:
    cfg = jarvis.config
    # In clone mode, make sure the local XTTS voice server is up before we start talking.
    if cfg.tts_engine == "clone":
        _ensure_clone_server(cfg)

    try:
        from .voice import Voice

        voice = Voice(
            tts_voice=cfg.tts_voice,
            tts_rate=cfg.tts_rate,
            engine=cfg.tts_engine,
            clone_url=cfg.clone_url,
            barge_in=cfg.barge_in,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Voice mode unavailable:[/red] {exc}")
        console.print("Install voice deps (see requirements.txt) or run without --voice.")
        sys.exit(1)

    # Rewire confirmation to spoken yes/no.
    tools.registry.confirm_callback = _make_voice_confirm(voice)

    name = jarvis.config.assistant_name
    owner = jarvis.config.owner
    wake_words = jarvis.config.wake_words
    wake_label = wake_words[0].title() if wake_words else name

    console.print(
        f"[bold green]{name}[/bold green] is running. Say [bold]'Hey {wake_label}'[/bold] once "
        "to start — then just keep talking, no need to repeat it. Say 'go to sleep' to pause, "
        "Ctrl+C to quit.\n"
    )
    voice.speak(
        f"{name} online. Say hey {wake_label} once to start, {owner}, then just talk to me."
    )

    try:
        while True:
            console.print(f"[dim]💤 waiting — say 'Hey {wake_label}'...[/dim]")
            heard = voice.listen()
            if not heard:
                continue

            # A bare exit phrase while idle quits without needing the wake word.
            if _is_exit(heard):
                voice.speak(_GOODBYE)
                return

            woke, command = _strip_wake_word(heard, wake_words)
            if not woke:
                # Show what it heard so you can tell it's listening (just not woken yet).
                console.print(f"[dim](heard: {heard})[/dim]")
                continue

            console.print(f"[bold cyan]You ›[/bold cyan] {heard}")
            # Just "Hey Jarvis" with nothing after → acknowledge, then listen in conversation.
            if not command:
                voice.speak(f"Yes {jarvis.config.owner}?")
            # Hand off to a flowing conversation. Returns True if JARVIS should quit entirely.
            if _converse(jarvis, voice, command):
                voice.speak(_GOODBYE)
                return
    except KeyboardInterrupt:
        console.print(f"\n{_GOODBYE}")


def _converse(jarvis: Jarvis, voice, first_command: str) -> bool:
    """Run a flowing conversation. Once awake, JARVIS keeps listening for your next request
    WITHOUT needing the wake word again — you just talk. It only stops when you say a sleep
    phrase ("go to sleep") or an exit phrase ("exit").

    Returns True if JARVIS should quit the program, False to go back to waiting for the wake word.
    """
    name = jarvis.config.assistant_name
    command = first_command

    while True:
        # Need something to respond to — listen for it (no wake word required mid-chat).
        if not command:
            console.print("[dim]🎤 listening (just talk — no wake word needed)...[/dim]")
            command = voice.listen()
            if not command:
                continue  # silence/noise — keep listening, stay awake
            console.print(f"[bold cyan]You ›[/bold cyan] {command}")

        if _is_exit(command):
            return True
        if _is_sleep(command):
            voice.speak("Okay, I'll be here if you need me. Just say my name.")
            return False
        if _is_new_chat(command):
            jarvis.reset()
            voice.speak("Okay, fresh start. What's on your mind?")
            command = ""
            continue

        with console.status("[dim]thinking...[/dim]"):
            reply = jarvis.chat(command)
        console.print(f"[bold green]{name} ›[/bold green] {reply}")
        console.print("[dim](press any key or talk to interrupt)[/dim]\n")
        # speak() returns what you said if you cut it off (keypress + speech, or voice barge-in);
        # handle that as the next turn instead of listening again.
        interrupted = voice.speak(reply, interrupt=True)
        if interrupted:
            console.print(f"[bold cyan]You ›[/bold cyan] {interrupted}  [dim](interrupted)[/dim]")
            command = interrupted
        else:
            command = ""  # listen for the next turn


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS desktop assistant")
    parser.add_argument("--voice", action="store_true", help="Use microphone + speaker")
    args = parser.parse_args()

    try:
        config = Config.load()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    # Default confirmation handler (text mode). Voice mode overrides it above.
    tools.registry.confirm_callback = _make_confirm()

    jarvis = Jarvis(config, on_tool=_on_tool)

    if args.voice:
        run_voice(jarvis)
    else:
        run_text(jarvis)


if __name__ == "__main__":
    main()
