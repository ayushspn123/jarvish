"""A tiny tool registry.

Each tool is a plain Python function decorated with @tool(...). The decorator records
an OpenAI-compatible JSON schema and the callable, so the brain can advertise tools to the
model and dispatch the model's tool calls back to Python.
"""

from __future__ import annotations

import json
import traceback
from typing import Any, Callable

# name -> {"schema": <openai tool schema>, "fn": <callable>, "confirm": bool}
_REGISTRY: dict[str, dict[str, Any]] = {}

# Set by main.py. Given a human-readable description of a destructive action, it must
# return True if the owner approves. Default denies, so nothing destructive runs unattended.
confirm_callback: Callable[[str], bool] = lambda _action: False


def tool(name: str, description: str, parameters: dict, *, confirm: bool = False) -> Callable:
    """Register a function as a tool.

    parameters: a JSON-Schema object describing the function's arguments.
    confirm:    if True, the owner must approve before the tool actually runs.
    """

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "fn": fn,
            "confirm": confirm,
        }
        return fn

    return decorator


def get_schemas() -> list[dict]:
    """Return all tool schemas, for the OpenAI `tools` parameter."""
    return [entry["schema"] for entry in _REGISTRY.values()]


def call_tool(name: str, arguments: dict) -> str:
    """Dispatch a tool call by name. Always returns a string (never raises) so the loop
    can hand the result back to the model even when something goes wrong."""
    entry = _REGISTRY.get(name)
    if entry is None:
        return f"ERROR: unknown tool '{name}'."

    if entry["confirm"]:
        action = f"{name}({json.dumps(arguments, ensure_ascii=False)})"
        if not confirm_callback(action):
            return "DENIED: the owner did not approve this action."

    try:
        return str(entry["fn"](**arguments))
    except TypeError as exc:
        return f"ERROR: bad arguments for '{name}': {exc}"
    except Exception as exc:  # noqa: BLE001 — tools must never crash the loop
        return f"ERROR running '{name}': {exc}\n{traceback.format_exc(limit=2)}"
