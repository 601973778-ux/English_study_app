from __future__ import annotations

from typing import Any

from Spoken_model.dialogue.contracts.protocols import KnowledgeRetriever, LlmAdapter, ScenarioPlugin
from Spoken_model.dialogue.contracts.types import SessionState


def _chunk_text(chunk: dict[str, Any]) -> str:
    for key in ("text_en", "text", "content"):
        val = chunk.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


class RagLlmEngine:
    def __init__(
        self,
        retriever: KnowledgeRetriever,
        llm: LlmAdapter | None,
        *,
        top_k: int = 5,
        llm_enabled: bool = True,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._top_k = top_k
        self._llm_enabled = llm_enabled

    def generate(
        self,
        plugin: ScenarioPlugin,
        user_text: str,
        session: SessionState,
    ) -> tuple[str, list[dict[str, Any]]]:
        query = plugin.rag_query(user_text, session)
        filters = plugin.rag_filters()
        hits = self._retriever.retrieve(query, filters=filters, top_k=self._top_k)
        if self._llm_enabled and self._llm is not None:
            reply = self._llm.chat(
                plugin.llm_system_prompt(session),
                self._build_messages(plugin, user_text, session, hits),
            )
            return reply.strip(), hits
        return self._template_reply(hits, user_text), hits

    def _build_messages(
        self,
        plugin: ScenarioPlugin,
        user_text: str,
        session: SessionState,
        hits: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        refs = []
        for h in hits[:3]:
            text = _chunk_text(h)
            if text:
                refs.append(f"- {text}")
        ref_block = "\n".join(refs) if refs else "- (no references)"
        system = (
            f"{plugin.llm_system_prompt(session)}\n\n"
            f"Reference snippets:\n{ref_block}\n"
            "Use references when helpful; keep replies natural and concise."
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for turn in session.transcript[-6:]:
            messages.append({"role": "user", "content": str(turn.get("user") or "")})
            messages.append({"role": "assistant", "content": str(turn.get("assistant") or "")})
        messages.append({"role": "user", "content": user_text})
        return messages

    def _template_reply(self, hits: list[dict[str, Any]], user_text: str) -> str:
        for h in hits:
            text = _chunk_text(h)
            if text and len(text) > 12:
                return f"Certainly. For example: {text[:180]}"
        return (
            "I'd be happy to help with your order. "
            "Would you like to see today's specials or start with a drink?"
        )
