"""System control tools: open/close applications and run shell commands.

Cross-platform where reasonable, but tuned for Windows (the owner's OS).
"""

from __future__ import annotations

import os
import platform
import subprocess

import psutil

from .registry import tool

_IS_WINDOWS = platform.system() == "Windows"

# Friendly name -> launch target. Extend freely.
_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
    "terminal": "wt" if _IS_WINDOWS else "x-terminal-emulator",
    "cmd": "cmd",
    "powershell": "powershell",
    "spotify": "spotify",
}


@tool(
    name="open_app",
    description=(
        "Open a desktop application by name (e.g. 'chrome', 'vs code', 'notepad', 'spotify'). "
        "Use this to launch programs."
    ),
    parameters={
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "Application name or executable."},
        },
        "required": ["app"],
    },
)
def open_app(app: str) -> str:
    target = _APP_ALIASES.get(app.strip().lower(), app.strip())
    try:
        if _IS_WINDOWS:
            # `start` resolves apps on PATH and registered app paths; shell=True needed for it.
            subprocess.Popen(f'start "" "{target}"', shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            subprocess.Popen([target])
        return f"Launched '{app}'."
    except Exception as exc:  # noqa: BLE001
        return f"Could not launch '{app}': {exc}"


@tool(
    name="close_app",
    description=(
        "Close/terminate a running application by process name (e.g. 'chrome', 'notepad', "
        "'code' for VS Code). Use this when the owner asks to close or quit an app."
    ),
    parameters={
        "type": "object",
        "properties": {
            "process_name": {
                "type": "string",
                "description": "Process or app name to terminate (without .exe).",
            },
        },
        "required": ["process_name"],
    },
)
def close_app(process_name: str) -> str:
    name = process_name.strip().lower().removesuffix(".exe")
    killed = 0
    for proc in psutil.process_iter(["name"]):
        pname = (proc.info["name"] or "").lower().removesuffix(".exe")
        if pname == name:
            try:
                proc.terminate()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    if killed == 0:
        return f"No running process named '{process_name}' was found."
    return f"Closed {killed} process(es) named '{process_name}'."


@tool(
    name="run_command",
    description=(
        "Run a shell command on the owner's machine and return its output. "
        "Destructive/powerful — requires owner confirmation. Use only when no safer tool fits."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The exact command line to run."},
        },
        "required": ["command"],
    },
    confirm=True,
)
def run_command(command: str) -> str:
    shell = ["powershell", "-NoProfile", "-Command", command] if _IS_WINDOWS else ["bash", "-lc", command]
    try:
        result = subprocess.run(
            shell, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return "Command timed out after 120s."
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    parts = [f"exit code: {result.returncode}"]
    if out:
        parts.append(f"stdout:\n{out[:4000]}")
    if err:
        parts.append(f"stderr:\n{err[:2000]}")
    return "\n".join(parts)


@tool(
    name="system_status",
    description="Report quick system stats: CPU %, memory usage, disk usage, and battery level.",
    parameters={"type": "object", "properties": {}},
)
def system_status() -> str:
    cpu = psutil.cpu_percent(interval=0.4)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.expanduser("~"))
    lines = [
        f"CPU: {cpu:.0f}%",
        f"Memory: {mem.percent:.0f}% used ({mem.used // 2**30} GB / {mem.total // 2**30} GB)",
        f"Disk (home): {disk.percent:.0f}% used ({disk.free // 2**30} GB free)",
    ]
    battery = getattr(psutil, "sensors_battery", lambda: None)()
    if battery is not None:
        plugged = "charging" if battery.power_plugged else "on battery"
        lines.append(f"Battery: {battery.percent:.0f}% ({plugged})")
    return "\n".join(lines)
