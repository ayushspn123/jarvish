"""Browser-driven Google actions: open Chrome, schedule meetings, join/start Google Meet,
open Google Chat / Gmail / Calendar.

These work with no API setup — they open the right page in Chrome (pre-filled where possible),
so the owner just clicks the final button. Full silent automation (creating events or sending
chat messages via the Google API) is a separate, OAuth-based upgrade.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import subprocess
import urllib.parse

from .registry import tool

_IS_WINDOWS = platform.system() == "Windows"


def _open_in_chrome(url: str) -> bool:
    """Open a URL specifically in Google Chrome. Returns False if Chrome couldn't be launched."""
    try:
        if _IS_WINDOWS:
            subprocess.Popen(f'start chrome "{url}"', shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", "Google Chrome", url])
        else:
            subprocess.Popen(["google-chrome", url])
        return True
    except Exception:  # noqa: BLE001
        return False


def _open_url(url: str) -> str:
    if _open_in_chrome(url):
        return f"Opened in Chrome: {url}"
    # Fall back to the default browser.
    import webbrowser

    webbrowser.open(url)
    return f"Opened in your default browser: {url}"


def _chrome_profiles() -> dict[str, str]:
    """Map friendly Chrome profile names -> profile directory (e.g. 'Default', 'Profile 1')."""
    import json

    out: dict[str, str] = {}
    local = os.environ.get("LOCALAPPDATA", "")
    state = os.path.join(local, "Google", "Chrome", "User Data", "Local State")
    try:
        with open(state, encoding="utf-8") as f:
            info = json.load(f).get("profile", {}).get("info_cache", {})
        for dir_name, meta in info.items():
            name = meta.get("name") or dir_name
            out[name.lower()] = dir_name
    except Exception:  # noqa: BLE001
        pass
    return out


@tool(
    name="list_chrome_profiles",
    description="List the Chrome profiles available on this PC (so the owner can pick one).",
    parameters={"type": "object", "properties": {}},
)
def list_chrome_profiles() -> str:
    profiles = _chrome_profiles()
    if not profiles:
        return "I couldn't read Chrome profiles. There may just be the default one."
    return "Chrome profiles: " + ", ".join(sorted(p.title() for p in profiles))


@tool(
    name="open_chrome_profile",
    description=(
        "Open Chrome using a specific profile (by its name, e.g. 'Ayush', 'Work', 'Default'), "
        "optionally at a URL. Use when the owner asks to open a particular profile/account."
    ),
    parameters={
        "type": "object",
        "properties": {
            "profile": {"type": "string", "description": "Profile name to open."},
            "url": {"type": "string", "description": "Optional URL to open in it."},
        },
        "required": ["profile"],
    },
)
def open_chrome_profile(profile: str, url: str = "") -> str:
    profiles = _chrome_profiles()
    dir_name = profiles.get(profile.strip().lower())
    if dir_name is None:
        # Try a loose contains match.
        for name, d in profiles.items():
            if profile.strip().lower() in name:
                dir_name = d
                break
    if dir_name is None:
        avail = ", ".join(sorted(p.title() for p in profiles)) or "Default"
        return f"No Chrome profile called '{profile}'. Available: {avail}."

    target = url if url.startswith("http") else (f"https://{url}" if url else "")
    cmd = f'start chrome --profile-directory="{dir_name}"'
    if target:
        cmd += f' "{target}"'
    subprocess.Popen(cmd, shell=True)
    return f"Opened Chrome profile '{profile}'" + (f" at {target}" if target else "") + "."


@tool(
    name="open_url",
    description="Open a web page (URL) in Chrome. Use for any website the owner names.",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "Full URL or domain."}},
        "required": ["url"],
    },
)
def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return _open_url(url)


@tool(
    name="play_on_youtube",
    description=(
        "Play a song or video on YouTube directly — finds the top result and opens the video "
        "itself (it starts playing), not just the search page. Use whenever the owner says to "
        "play music or a video, e.g. 'play Chand Sifarish', 'play the first one'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Song/video to play."},
        },
        "required": ["query"],
    },
)
def play_on_youtube(query: str) -> str:
    import re

    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": query},
            headers=headers,
            timeout=15,
        )
        ids = re.findall(r'"videoId":"([\w-]{11})"', resp.text)
    except Exception:  # noqa: BLE001
        ids = []

    if ids:
        _open_url(f"https://www.youtube.com/watch?v={ids[0]}")
        return f"Playing the top result for '{query}' on YouTube."
    # Couldn't find a video — fall back to the search page.
    q = urllib.parse.quote_plus(query)
    _open_url(f"https://www.youtube.com/results?search_query={q}")
    return f"I couldn't grab a direct video, so I opened the search for '{query}'."


@tool(
    name="open_website",
    description=(
        "Open a known site in Chrome by name: 'youtube', 'gmail', 'google calendar', "
        "'google chat', 'google meet', 'linkedin', 'github', 'maps', 'drive'."
    ),
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Site name."}},
        "required": ["name"],
    },
)
def open_website(name: str) -> str:
    sites = {
        "youtube": "https://youtube.com",
        "gmail": "https://mail.google.com",
        "google calendar": "https://calendar.google.com",
        "calendar": "https://calendar.google.com",
        "google chat": "https://chat.google.com",
        "chat": "https://chat.google.com",
        "google meet": "https://meet.google.com",
        "meet": "https://meet.google.com",
        "linkedin": "https://linkedin.com",
        "github": "https://github.com",
        "maps": "https://maps.google.com",
        "drive": "https://drive.google.com",
    }
    url = sites.get(name.strip().lower())
    if not url:
        return f"I don't have a shortcut for '{name}'. Give me a URL and I'll open it."
    return _open_url(url)


@tool(
    name="start_google_meet",
    description="Start a brand-new Google Meet meeting in Chrome (opens meet.new).",
    parameters={"type": "object", "properties": {}},
)
def start_google_meet() -> str:
    _open_url("https://meet.new")
    return "Starting a new Google Meet in Chrome."


@tool(
    name="join_google_meet",
    description=(
        "Actually join an existing Google Meet — opens it and clicks Join for the owner. "
        "Accepts a full meet link or just the meeting code (e.g. 'abc-defg-hij')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "meeting": {"type": "string", "description": "Meet URL or meeting code."}
        },
        "required": ["meeting"],
    },
)
def join_google_meet(meeting: str) -> str:
    # Try real auto-join (clicks "Join now") via the automated browser.
    try:
        from .meet import join_meeting_browser

        ok, message = join_meeting_browser(meeting)
        if ok:
            return message
        # Auto-join failed (e.g. not signed in yet) — fall back to just opening the page.
        m = meeting.strip()
        if not m.startswith("http"):
            m = "https://meet.google.com/" + m.replace(" ", "").lstrip("/")
        _open_url(m)
        return message
    except Exception as exc:  # noqa: BLE001 — Playwright missing/broken: just open the link
        m = meeting.strip()
        if not m.startswith("http"):
            m = "https://meet.google.com/" + m.replace(" ", "").lstrip("/")
        _open_url(m)
        return f"Opened the meeting in Chrome (auto-join unavailable: {exc})."


@tool(
    name="schedule_meeting",
    description=(
        "Schedule a meeting/event on Google Calendar. Opens Calendar in Chrome with the event "
        "pre-filled (title, time, guests, description) — the owner just clicks Save. "
        "Provide start/end as ISO datetimes like '2026-06-10T15:00:00'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title."},
            "start": {"type": "string", "description": "Start time, ISO 8601 (local)."},
            "end": {"type": "string", "description": "End time, ISO 8601. Defaults to +30 min."},
            "attendees": {
                "type": "string",
                "description": "Comma-separated guest emails (optional).",
            },
            "description": {"type": "string", "description": "Event details (optional)."},
            "timezone": {
                "type": "string",
                "description": "IANA timezone. Defaults to Asia/Kolkata.",
            },
        },
        "required": ["title", "start"],
    },
)
def schedule_meeting(
    title: str,
    start: str,
    end: str = "",
    attendees: str = "",
    description: str = "",
    timezone: str = "Asia/Kolkata",
) -> str:
    def _fmt(iso: str) -> str:
        # "2026-06-10T15:00:00" -> "20260610T150000"
        dt = _dt.datetime.fromisoformat(iso)
        return dt.strftime("%Y%m%dT%H%M%S")

    try:
        start_fmt = _fmt(start)
        if end:
            end_fmt = _fmt(end)
        else:
            end_dt = _dt.datetime.fromisoformat(start) + _dt.timedelta(minutes=30)
            end_fmt = end_dt.strftime("%Y%m%dT%H%M%S")
    except ValueError:
        return f"I couldn't read the time. Please give it like '2026-06-10T15:00:00'. Got: {start}"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_fmt}/{end_fmt}",
        "ctz": timezone,
    }
    if description:
        params["details"] = description
    if attendees:
        params["add"] = attendees.replace(" ", "")

    url = "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)
    _open_url(url)
    return (
        f"Opened Google Calendar in Chrome with '{title}' pre-filled for {start}. "
        "Just review the guests and click Save."
    )
