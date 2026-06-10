"""The brain: an OpenAI tool-calling loop.

Holds the conversation, sends it to the model with the available tools, executes any tool
calls the model requests, feeds the results back, and repeats until the model produces a
final natural-language reply.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Callable

from openai import OpenAI

from .config import SYSTEM_PROMPT, Config
from .tools import call_tool, get_schemas

# Safety valve: stop runaway tool loops.
_MAX_STEPS = 12


class Jarvis:
    def __init__(self, config: Config, on_tool: Callable[[str, dict], None] | None = None):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key, base_url=config.base_url)
        # on_tool(name, args) is an optional UI hook so the CLI can show "running X...".
        self.on_tool = on_tool or (lambda name, args: None)

        today = _dt.date.today().isoformat()
        system = (
            SYSTEM_PROMPT.format(name=config.assistant_name, owner=config.owner)
            + f"\nToday's date: {today}."
        )
        self._system_message = {"role": "system", "content": system}
        self.messages: list[dict] = [self._system_message]

    def reset(self) -> None:
        """Forget the current conversation and start fresh (keeps the system prompt)."""
        self.messages = [self._system_message]

    def chat(self, user_input: str) -> str:
        """Send one user turn through the tool loop and return the final reply text."""
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(_MAX_STEPS):
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.messages,
                tools=get_schemas(),
                tool_choice="auto",
            )
            message = response.choices[0].message

            # Record the assistant turn (including any tool calls) verbatim.
            self.messages.append(_message_to_dict(message))

            if not message.tool_calls:
                return message.content or ""

            # Execute every requested tool call and append a tool result for each.
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                self.on_tool(tc.function.name, args)
                result = call_tool(tc.function.name, args)
                self.messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

        return "I stopped after too many internal steps. Could you narrow the request?"


def _message_to_dict(message) -> dict:
    """Convert an OpenAI message object into a plain dict suitable for re-sending."""
    data: dict = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
    return data
