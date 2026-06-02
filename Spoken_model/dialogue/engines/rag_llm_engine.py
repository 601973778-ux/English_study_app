from __future__ import annotations

import random
from typing import Any

from Spoken_model.dialogue.contracts.protocols import KnowledgeRetriever, LlmAdapter, ScenarioPlugin
from Spoken_model.dialogue.contracts.types import SessionState


def _chunk_text(chunk: dict[str, Any]) -> str:
    for key in ("text_en", "text", "content"):
        val = chunk.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


_WAITER_SPEAKERS = frozenset({"W", "WAITER", "S", "STAFF", "B", "BARISTA", "HOST"})


def _is_waiter_hit(hit: dict[str, Any]) -> bool:
    if hit.get("chunk_type") != "dialogue_turn":
        return False
    speaker = str(hit.get("speaker") or "").upper()
    return speaker in _WAITER_SPEAKERS


class RagLlmEngine:
    def __init__(
        self,
        retriever: KnowledgeRetriever,
        llm: LlmAdapter | None,
        *,
        top_k: int = 5,
        llm_enabled: bool = True,
        rag_min_score: float = 0.0,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._top_k = top_k
        self._llm_enabled = llm_enabled
        self._rag_min_score = rag_min_score

    def generate(
        self,
        plugin: ScenarioPlugin,
        user_text: str,
        session: SessionState,
    ) -> tuple[str, list[dict[str, Any]]]:
        query = plugin.rag_query(user_text, session)
        filters = plugin.rag_filters()
        hits = self._retriever.retrieve(query, filters=filters, top_k=self._top_k)
        hits = _filter_hits_by_score(hits, self._rag_min_score)
        if self._llm_enabled and self._llm is not None:
            reply = self._llm.chat(
                plugin.llm_system_prompt(session),
                self._build_messages(plugin, user_text, session, hits),
            )
            return reply.strip(), hits
        return self._template_reply(hits, user_text), hits

    def generate_opening(
        self,
        plugin: ScenarioPlugin,
        session: SessionState,
        *,
        opening_rag_query: str,
        opening_rag_filters: dict[str, Any],
        opening_fallback: str,
        opening_system_prompt: str,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        """RAG + optional LLM for session opening line. Returns (text, source, hits)."""
        hits = self._retriever.retrieve(
            opening_rag_query,
            filters=opening_rag_filters,
            top_k=self._top_k,
        )
        hits = _filter_hits_by_score(hits, self._rag_min_score)
        waiter_hits = [h for h in hits if _is_waiter_hit(h)] or list(hits)
        waiter_hits = list(waiter_hits)
        random.shuffle(waiter_hits)

        if self._llm_enabled and self._llm is not None:
            try:
                reply = self._llm.chat(
                    opening_system_prompt,
                    self._build_opening_messages(opening_system_prompt, waiter_hits),
                ).strip()
                if reply:
                    return reply, "rag_llm", hits
            except Exception:
                pass

        template = self._opening_template_reply(waiter_hits)
        if template:
            return template, "rag_template", hits
        return opening_fallback, "fallback", hits

    def _build_opening_messages(
        self,
        system_prompt: str,
        hits: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        refs = []
        for h in hits[:5]:
            text = _chunk_text(h)
            if text:
                refs.append(f"- {text}")
        ref_block = "\n".join(refs) if refs else "- (no references)"
        system = (
            f"{system_prompt}\n\n"
            f"Reference snippets:\n{ref_block}\n\n"
            "Generate ONE waiter opening line (1-2 short sentences). "
            "Greet the customer and ask about table size, reservation, or how you can help. "
            "Use the reference phrases when helpful; vary wording when possible; "
            "do not invent menu items or prices."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "The customer just walked in. Say your opening greeting."},
        ]

    def _opening_template_reply(self, hits: list[dict[str, Any]]) -> str:
        pool = [h for h in hits if _is_waiter_hit(h)] or list(hits)
        random.shuffle(pool)
        for h in pool:
            text = _chunk_text(h)
            if text and len(text) > 8:
                return text[:280]
        return ""

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
            if not text or len(text) <= 12:
                continue
            if h.get("chunk_type") == "dialogue_turn" and h.get("speaker"):
                speaker = str(h.get("speaker") or "").upper()
                if speaker in ("W", "WAITER", "S", "STAFF", "B", "BARISTA"):
                    return text[:280]
            if h.get("chunk_type") == "useful_expression":
                return text[:280]
        for h in hits:
            text = _chunk_text(h)
            if text and len(text) > 12:
                return text[:280]
        return (
            "I'd be happy to help with your order. "
            "Would you like to see today's specials or start with a drink?"
        )


def _filter_hits_by_score(hits: list[dict[str, Any]], min_score: float) -> list[dict[str, Any]]:
    if min_score <= 0:
        return hits
    return [h for h in hits if float(h.get("score") or 0) >= min_score]
