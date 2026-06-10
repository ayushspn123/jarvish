"""Actually join a Google Meet (click "Join now") via browser automation.

The automation runs in a SEPARATE process (jarvis/meet_join.py) so Playwright's event loop can't
interfere with the app's voice/async work. It uses a dedicated, persistent Chrome profile
(`chrome_profile/`) — sign into Google there once and after that it auto-joins. The joiner
process stays alive so you remain in the call.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_JARVIS_PROFILE = os.path.join(_ROOT, "chrome_profile")


def _real_chrome_profile() -> tuple[str, str]:
    """Path to the owner's real Chrome 'User Data' dir and the 'Default' profile (signed in)."""
    local = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(local, "Google", "Chrome", "User Data"), "Default"


def _normalize(meeting: str) -> str:
    m = meeting.strip()
    if not m.startswith("http"):
        m = "https://meet.google.com/" + m.replace(" ", "").lstrip("/")
    return m


def join_meeting_browser(meeting: str) -> tuple[bool, str]:
    """Spawn the detached joiner process, wait briefly for it to click Join. Returns (ok, msg).

    Uses the owner's real, signed-in Chrome profile so their Google account is available.
    (Chrome must not already be running on that profile, or it's locked — we fall back then.)
    """
    link = _normalize(meeting)
    fd, status_file = tempfile.mkstemp(suffix=".meetstatus")
    os.close(fd)
    log_path = os.path.join(_ROOT, "voice_clone", "meet_join.log")

    user_data, profile_dir = _real_chrome_profile()
    if not os.path.isdir(user_data):
        user_data, profile_dir = _JARVIS_PROFILE, ""

    # DETACHED_PROCESS so the meeting browser survives independently of JARVIS.
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    try:
        log = open(log_path, "w")
    except OSError:
        log = subprocess.DEVNULL

    cmd = [sys.executable, "-m", "jarvis.meet_join", link, status_file, user_data]
    if profile_dir:
        cmd.append(profile_dir)
    subprocess.Popen(
        cmd,
        cwd=_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=True,
    )

    return _await_status(status_file)


def _await_status(status_file: str) -> tuple[bool, str]:
    """Poll the joiner's status file for up to ~40s and turn it into a (ok, message)."""
    for _ in range(80):
        status = ""
        try:
            with open(status_file, encoding="utf-8") as f:
                status = f.read().strip()
        except OSError:
            status = ""
        if status.startswith("ok"):
            return True, "Joined the meeting — you're in."
        if status.startswith("fail"):
            return False, (
                "I opened the meeting but couldn't click Join. If Chrome was already open, "
                "close it and ask me to join again so I can use your signed-in profile."
            )
        time.sleep(0.5)
    # Took longer than expected — it's probably still joining.
    return True, "Opening and joining the meeting now — it'll be up in a moment."
