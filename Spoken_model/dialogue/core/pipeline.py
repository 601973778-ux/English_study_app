from __future__ import annotations

import base64

from Spoken_model.dialogue.contracts.protocols import (
    AsrAdapter,
    KnowledgeRetriever,
    LlmAdapter,
    ScenarioPlugin,
    TtsAdapter,
)
from Spoken_model.dialogue.contracts.types import RouteKind, SessionState, TurnRequest, TurnResult
from Spoken_model.dialogue.core.cycle_manager import increment_user_turn
from Spoken_model.dialogue.core.text_normalizer import normalize_user_text
from Spoken_model.dialogue.engines.rag_llm_engine import RagLlmEngine
from Spoken_model.dialogue.engines.script_engine import ScriptEngine


class TurnPipeline:
    def __init__(
        self,
        *,
        asr: AsrAdapter,
        tts: TtsAdapter,
        retriever: KnowledgeRetriever,
        llm: LlmAdapter | None,
        llm_enabled: bool = True,
    ) -> None:
        self._asr = asr
        self._tts = tts
        self._script = ScriptEngine()
        self._rag = RagLlmEngine(retriever, llm, llm_enabled=llm_enabled)

    def resolve_user_text(self, req: TurnRequest) -> str:
        text = normalize_user_text(req.user_text or "")
        if text:
            return text
        if req.audio_b64:
            audio = base64.b64decode(req.audio_b64)
            return normalize_user_text(self._asr.transcribe(audio))
        return ""

    def run_turn(
        self,
        plugin: ScenarioPlugin,
        session: SessionState,
        user_text: str,
    ) -> TurnResult:
        route = plugin.classify(user_text, session)
        reply: str | None = None
        next_stage: str | None = None
        meta: dict = {"route": route.value}

        if route != RouteKind.RAG_LLM:
            reply, next_stage = self._script.try_reply(plugin, user_text, session, route)

        if route == RouteKind.RAG_LLM or reply is None:
            route = RouteKind.RAG_LLM
            reply, hits = self._rag.generate(plugin, user_text, session)
            meta["rag_hits"] = [
                {"score": h.get("score"), "chunk_type": h.get("chunk_type"), "topic_id": h.get("topic_id")}
                for h in hits[:3]
            ]

        if next_stage:
            session.stage = next_stage

        session = plugin.on_turn_end(user_text, reply, session, route)
        session, eval_ready = increment_user_turn(session)

        tts_url = self._tts.tts_url_for(reply) or None
        return TurnResult(
            session_id=session.session_id,
            scenario_id=session.scenario_id,
            waiter_reply=reply,
            route=route,
            stage=session.stage,
            user_count_in_cycle=session.user_count_in_cycle,
            cycle_index=session.cycle_index,
            cycle_evaluation_ready=eval_ready,
            tts_url=tts_url,
            meta=meta,
        )
