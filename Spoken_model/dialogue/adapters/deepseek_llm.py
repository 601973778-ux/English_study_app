from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class DeepSeekLlmError(RuntimeError):
    pass


class DeepSeekLlm:
    """OpenAI-compatible chat completions (DeepSeek cloud or local vLLM/Ollama)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_sec: int = 60,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key.strip()
        self.timeout_sec = timeout_sec
        self.max_tokens = max_tokens
        self.temperature = temperature

    def chat(self, system: str, messages: list[dict[str, str]]) -> str:
        payload_messages = _normalize_messages(system, messages)
        body = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise DeepSeekLlmError(f"LLM HTTP {e.code}: {detail[:500]}") from e
        except urllib.error.URLError as e:
            raise DeepSeekLlmError(f"LLM request failed: {e.reason}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekLlmError("LLM returned invalid JSON") from e

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise DeepSeekLlmError(f"Unexpected LLM response: {raw[:500]}") from e

        text = str(content or "").strip()
        if not text:
            raise DeepSeekLlmError("LLM returned empty content")
        return text


def _normalize_messages(system: str, messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if messages and messages[0].get("role") == "system":
        out.extend({"role": str(m["role"]), "content": str(m.get("content") or "")} for m in messages)
    else:
        sys_text = (system or "").strip()
        if sys_text:
            out.append({"role": "system", "content": sys_text})
        for m in messages:
            role = str(m.get("role") or "user")
            content = str(m.get("content") or "")
            if role == "system" and out and out[0]["role"] == "system":
                out[0]["content"] = f"{out[0]['content']}\n\n{content}".strip()
            elif content:
                out.append({"role": role, "content": content})
    return [m for m in out if m.get("content")]
