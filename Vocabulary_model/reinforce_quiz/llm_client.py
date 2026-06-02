from __future__ import annotations

from Spoken_model.dialogue.adapters.deepseek_llm import DeepSeekLlmError
from Spoken_model.dialogue.adapters.llm_factory import create_llm_adapter


def chat(system: str, user: str, *, max_tokens: int = 256) -> str:
    llm, enabled, cfg = create_llm_adapter()
    if not enabled:
        raise DeepSeekLlmError(
            "未启用 LLM：请在「API 接入配置」中启用 DeepSeek/OpenAI 兼容 LLM"
        )
    old_max = llm.max_tokens
    try:
        llm.max_tokens = max_tokens
        return llm.chat(system, [{"role": "user", "content": user}])
    finally:
        llm.max_tokens = old_max


def try_chat(system: str, user: str, *, max_tokens: int = 256) -> str | None:
    try:
        return chat(system, user, max_tokens=max_tokens)
    except (DeepSeekLlmError, RuntimeError, OSError, ValueError):
        return None
