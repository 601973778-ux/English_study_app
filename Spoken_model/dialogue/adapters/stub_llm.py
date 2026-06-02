from __future__ import annotations

from typing import Any


class StubLlm:
    """Template fallback until DeepSeek local deployment is wired."""

    def chat(self, system: str, messages: list[dict[str, str]]) -> str:
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        last_user = user_msgs[-1] if user_msgs else ""
        refs = _extract_reference_snippets(messages)
        if refs:
            snippet = refs[0][:220].strip()
            return (
                f"Sure. {snippet} "
                f"Could you tell me a bit more about what you'd like?"
            )
        if last_user:
            return (
                "I understand. Let me help you with that. "
                "Would you like to see the menu or order something?"
            )
        return "Hello! Welcome. How can I help you today?"


def _extract_reference_snippets(messages: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for m in messages:
        if m.get("role") != "system":
            continue
        text = m.get("content") or ""
        marker = "Reference snippets:"
        if marker in text:
            block = text.split(marker, 1)[1].strip()
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    out.append(line[2:])
    return out
