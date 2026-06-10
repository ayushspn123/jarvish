"""Real Google Calendar integration (via the Google API, with a one-time sign-in).

Lets JARVIS read your actual calendar — e.g. list today's meetings so you can pick one to join —
and create events directly. Needs a Google OAuth client:

  1. Go to https://console.cloud.google.com/ , create a project.
  2. Enable the "Google Calendar API".
  3. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID -> Desktop app.
  4. Download the JSON and save it as `credentials.json` in the project root.

The first call opens a browser to sign in; the token is then cached in `google_token.json`.
Until credentials.json exists, these tools return a friendly message explaining the setup.
"""

from __future__ import annotations

import datetime as _dt
import os

from .registry import tool

# Calendar read + write (create events).
_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CRED_PATH = os.path.join(_ROOT, "credentials.json")
_TOKEN_PATH = os.path.join(_ROOT, "google_token.json")

_SETUP_HELP = (
    "Google Calendar isn't connected yet. To enable it: create an OAuth 'Desktop app' client at "
    "console.cloud.google.com (enable the Google Calendar API), download the JSON, and save it as "
    "credentials.json in the JARVIS folder. Then ask me again and I'll open a sign-in once."
)


def _get_service():
    """Build an authenticated Calendar service, running the OAuth flow on first use."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(_CRED_PATH):
                raise FileNotFoundError(_SETUP_HELP)
            flow = InstalledAppFlow.from_client_secrets_file(_CRED_PATH, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def _meet_link(event: dict) -> str:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for ep in event.get("conferenceData", {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri", "")
    return ""


@tool(
    name="list_todays_meetings",
    description=(
        "List the owner's Google Calendar meetings for today, with their times and any video/"
        "Meet links. Use this when asked to join a meeting or 'what's on my calendar today' — "
        "then ask which one to join and use join_google_meet with that link."
    ),
    parameters={"type": "object", "properties": {}},
)
def list_todays_meetings() -> str:
    try:
        service = _get_service()
    except FileNotFoundError as exc:
        return str(exc)

    tz = _dt.datetime.now().astimezone().tzinfo
    start = _dt.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + _dt.timedelta(days=1)
    events = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    if not events:
        return "You have no meetings on your calendar today."

    lines = []
    for i, ev in enumerate(events, 1):
        s = ev["start"].get("dateTime", ev["start"].get("date", ""))
        try:
            when = _dt.datetime.fromisoformat(s).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            when = "all day"
        title = ev.get("summary", "(no title)")
        link = _meet_link(ev)
        lines.append(f"{i}. {when} — {title}" + (f"  [link: {link}]" if link else "  [no video link]"))
    return "Today's meetings:\n" + "\n".join(lines)


@tool(
    name="create_calendar_event",
    description=(
        "Create an event directly on the owner's Google Calendar (no manual Save needed). "
        "Use when they clearly want it booked. Times are ISO 8601 like '2026-06-10T15:00:00'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "ISO start datetime."},
            "end": {"type": "string", "description": "ISO end datetime. Defaults to +30 min."},
            "attendees": {"type": "string", "description": "Comma-separated guest emails."},
            "description": {"type": "string"},
        },
        "required": ["title", "start"],
    },
    confirm=True,
)
def create_calendar_event(
    title: str, start: str, end: str = "", attendees: str = "", description: str = ""
) -> str:
    try:
        service = _get_service()
    except FileNotFoundError as exc:
        return str(exc)

    try:
        start_dt = _dt.datetime.fromisoformat(start)
        end_dt = _dt.datetime.fromisoformat(end) if end else start_dt + _dt.timedelta(minutes=30)
    except ValueError:
        return f"Couldn't read the time; use '2026-06-10T15:00:00'. Got: {start}"

    tz = str(_dt.datetime.now().astimezone().tzinfo)
    body = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
    }
    if description:
        body["description"] = description
    if attendees:
        body["attendees"] = [{"email": e.strip()} for e in attendees.split(",") if e.strip()]

    ev = service.events().insert(calendarId="primary", body=body).execute()
    return f"Booked '{title}' for {start_dt.strftime('%b %d, %I:%M %p')}. Link: {ev.get('htmlLink', '')}"
