from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteKind(str, Enum):
    SCRIPT_CONTROL = "script_control"
    SCRIPT_CHITCHAT = "script_chitchat"
    SCRIPT_TOPIC = "script_topic"
    RAG_LLM = "rag_llm"
    REDIRECT = "redirect"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    AWAITING_EVAL = "awaiting_eval"
    ENDED = "ended"


@dataclass
class TurnRequest:
    session_id: str
    user_text: str | None = None
    audio_b64: str | None = None


@dataclass
class TurnResult:
    session_id: str
    scenario_id: str
    waiter_reply: str
    route: RouteKind
    stage: str
    user_count_in_cycle: int
    cycle_index: int
    cycle_evaluation_ready: bool
    tts_url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "waiter_reply": self.waiter_reply,
            "route": self.route.value,
            "stage": self.stage,
            "user_count_in_cycle": self.user_count_in_cycle,
            "cycle_index": self.cycle_index,
            "cycle_evaluation_ready": self.cycle_evaluation_ready,
            "tts_url": self.tts_url,
            "meta": self.meta,
        }


@dataclass
class SessionState:
    session_id: str
    scenario_id: str
    stage: str
    cycle_index: int
    user_count_in_cycle: int
    cycle_size: int
    status: SessionStatus
    transcript: list[dict[str, Any]] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "stage": self.stage,
            "cycle_index": self.cycle_index,
            "user_count_in_cycle": self.user_count_in_cycle,
            "cycle_size": self.cycle_size,
            "status": self.status.value,
            "transcript": self.transcript,
            "slots": self.slots,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SessionState:
        return cls(
            session_id=str(raw["session_id"]),
            scenario_id=str(raw["scenario_id"]),
            stage=str(raw.get("stage", "GREETING")),
            cycle_index=int(raw.get("cycle_index", 1)),
            user_count_in_cycle=int(raw.get("user_count_in_cycle", 0)),
            cycle_size=int(raw.get("cycle_size", 10)),
            status=SessionStatus(str(raw.get("status", SessionStatus.ACTIVE.value))),
            transcript=list(raw.get("transcript") or []),
            slots=dict(raw.get("slots") or {}),
        )
