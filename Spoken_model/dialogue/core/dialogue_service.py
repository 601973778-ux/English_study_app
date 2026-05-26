from __future__ import annotations

from pathlib import Path

from Spoken_model.dialogue.adapters.passthrough_asr import PassthroughAsr
from Spoken_model.dialogue.adapters.rag_retriever import TfidfKnowledgeRetriever
from Spoken_model.dialogue.adapters.server_tts import ServerTtsAdapter
from Spoken_model.dialogue.adapters.stub_llm import StubLlm
from Spoken_model.dialogue.contracts.types import SessionState, SessionStatus, TurnRequest, TurnResult
from Spoken_model.dialogue.core.cycle_manager import continue_cycle, end_session
from Spoken_model.dialogue.core.pipeline import TurnPipeline
from Spoken_model.dialogue.core.registry import get_scenario, list_scenarios
from Spoken_model.dialogue.core.session_store import SessionStore
from Spoken_model.dialogue.evaluation.rule_evaluator import evaluate_cycle
from Spoken_model.dialogue.scenarios.loader import JsonScenarioPlugin

DIALOGUE_ROOT = Path(__file__).resolve().parent.parent
USER_DATA = DIALOGUE_ROOT / "user_data" / "sessions"


class DialogueService:
    def __init__(self, *, llm_enabled: bool = False) -> None:
        self._store = SessionStore(USER_DATA)
        self._tts = ServerTtsAdapter()
        self._pipeline = TurnPipeline(
            asr=PassthroughAsr(),
            tts=self._tts,
            retriever=TfidfKnowledgeRetriever(),
            llm=StubLlm(),
            llm_enabled=llm_enabled,
        )

    def scenarios(self) -> list[dict[str, str]]:
        return list_scenarios()

    def start(self, scenario_id: str) -> dict:
        plugin = get_scenario(scenario_id)
        assert isinstance(plugin, JsonScenarioPlugin)
        session = self._store.create(
            scenario_id=plugin.scenario_id,
            cycle_size=plugin.cycle_size,
            default_stage=plugin.default_stage,
        )
        opening = plugin.opening_line(session)
        session.transcript.append(
            {"user": "", "assistant": opening, "route": "opening", "stage": session.stage}
        )
        self._store.save(session)
        tts_url = self._tts.tts_url_for(opening) or None
        return {
            "session_id": session.session_id,
            "scenario_id": session.scenario_id,
            "opening_line": opening,
            "stage": session.stage,
            "cycle_size": session.cycle_size,
            "tts_url": tts_url,
        }

    def turn(self, req: TurnRequest) -> TurnResult:
        session = self._require_session(req.session_id)
        if session.status != SessionStatus.ACTIVE:
            raise ValueError("session is not active; continue or start a new one")
        user_text = self._pipeline.resolve_user_text(req)
        if not user_text:
            raise ValueError("user_text or audio_b64 required")
        plugin = get_scenario(session.scenario_id)
        result = self._pipeline.run_turn(plugin, session, user_text)
        self._store.save(session)
        return result

    def evaluation(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        plugin = get_scenario(session.scenario_id)
        report = evaluate_cycle(plugin, session)
        report["session_id"] = session_id
        report["status"] = session.status.value
        return report

    def continue_session(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        if session.status != SessionStatus.AWAITING_EVAL:
            raise ValueError("session is not awaiting evaluation")
        session = continue_cycle(session)
        self._store.save(session)
        return {"session_id": session_id, "cycle_index": session.cycle_index, "status": session.status.value}

    def end(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        session = end_session(session)
        self._store.save(session)
        return {"session_id": session_id, "status": session.status.value}

    def session_state(self, session_id: str) -> SessionState:
        return self._require_session(session_id)

    def _require_session(self, session_id: str) -> SessionState:
        session = self._store.get(session_id)
        if session is None:
            raise KeyError("session not found")
        return session


_SERVICE: DialogueService | None = None


def get_dialogue_service() -> DialogueService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = DialogueService(llm_enabled=False)
    return _SERVICE
