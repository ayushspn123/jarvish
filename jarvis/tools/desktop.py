"""Desktop GUI control: focus windows, press hotkeys, type text, take screenshots.

This is what lets JARVIS operate any app on the laptop the way you would — e.g. focus VS Code,
open a new tab with Ctrl+T, open the command palette with Ctrl+Shift+P, type a command, etc.
Actions happen on the laptop's screen (controllable from your phone via the web app).
"""

from __future__ import annotations

import time

import pyautogui

from .registry import tool

pyautogui.FAILSAFE = False  # don't abort if the cursor hits a screen corner


@tool(
    name="focus_window",
    description=(
        "Bring an app's window to the front so keystrokes go to it. Match by part of the title, "
        "e.g. 'Visual Studio Code', 'Chrome', 'Notepad'. Do this before typing or hotkeys."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Part of the window title to focus."}
        },
        "required": ["title"],
    },
)
def focus_window(title: str) -> str:
    import pygetwindow as gw

    matches = [w for w in gw.getAllWindows() if title.lower() in (w.title or "").lower()]
    if not matches:
        return f"No open window matching '{title}'. Open the app first."
    win = matches[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
    except Exception:  # noqa: BLE001 — activation can be finicky on Windows
        try:
            win.minimize()
            win.restore()
        except Exception:  # noqa: BLE001
            pass
    time.sleep(0.4)
    return f"Focused '{win.title}'."


@tool(
    name="press_hotkey",
    description=(
        "Press a keyboard shortcut in the focused app. Give keys joined by '+', e.g. 'ctrl+t' "
        "(new tab), 'ctrl+shift+p' (command palette), 'alt+tab', 'ctrl+s'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "keys": {"type": "string", "description": "Hotkey like 'ctrl+shift+p'."}
        },
        "required": ["keys"],
    },
)
def press_hotkey(keys: str) -> str:
    parts = [k.strip().lower() for k in keys.replace(" ", "").split("+") if k.strip()]
    if not parts:
        return "No keys given."
    pyautogui.hotkey(*parts)
    time.sleep(0.2)
    return f"Pressed {'+'.join(parts)}."


@tool(
    name="press_key",
    description="Press a single key like 'enter', 'esc', 'tab', 'down', 'f5'.",
    parameters={
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key name."}},
        "required": ["key"],
    },
)
def press_key(key: str) -> str:
    pyautogui.press(key.strip().lower())
    time.sleep(0.15)
    return f"Pressed {key}."


@tool(
    name="type_text",
    description=(
        "Type text into the focused window/field, as if typed on the keyboard. Use after "
        "focusing the right app or field."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to type."},
            "press_enter": {
                "type": "boolean",
                "description": "Press Enter after typing (default false).",
            },
        },
        "required": ["text"],
    },
)
def type_text(text: str, press_enter: bool = False) -> str:
    # Paste via clipboard for reliability with long text / unicode, then optionally Enter.
    try:
        import pyperclip

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except Exception:  # noqa: BLE001 — fall back to direct typing
        pyautogui.typewrite(text, interval=0.01)
    if press_enter:
        time.sleep(0.1)
        pyautogui.press("enter")
    return f"Typed {len(text)} characters."
