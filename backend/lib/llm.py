"""Claude Code CLI helpers — delegates LLM work to `claude -p`."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any

log = logging.getLogger(__name__)


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.get("role", "user").upper()
        parts.append(f"{role}:\n{message.get('content', '')}")
    return "\n\n".join(parts)


class LLMClient:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def complete(self, prompt: str, temperature: float = 0.2, max_tokens: int = 4000) -> str:
        del temperature, max_tokens
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", self.model],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data["result"].strip()

    def complete_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> str:
        return self.complete(
            _messages_to_prompt(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_json(self, prompt: str, temperature: float = 0.0, max_tokens: int = 4000) -> Any:
        return self.complete_json_messages(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_json_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> Any:
        text = self.complete_messages(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parse_json_response(text)


def parse_json_response(text: str) -> Any:
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start < 0:
            raise
        obj, _end = json.JSONDecoder().raw_decode(cleaned[start:])
        return obj
