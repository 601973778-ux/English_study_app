from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from Spoken_model.dialogue.contracts.types import RouteKind, SessionState


@runtime_checkable
class ScenarioPlugin(Protocol):
    scenario_id: str
    title_zh: str
    title_en: str

    def opening_line(self, session: SessionState) -> str: ...

    def classify(self, user_text: str, session: SessionState) -> RouteKind: ...

    def try_script(
        self, user_text: str, session: SessionState, route: RouteKind
    ) -> tuple[str | None, str | None]: ...

    def on_turn_end(
        self, user_text: str, reply: str, session: SessionState, route: RouteKind
    ) -> SessionState: ...

    def rag_query(self, user_text: str, session: SessionState) -> str: ...

    def rag_filters(self) -> dict[str, Any]: ...

    def llm_system_prompt(self, session: SessionState) -> str: ...

    def coverage_checklist(self) -> list[dict[str, Any]]: ...

    def topic_keywords(self) -> set[str]: ...


@runtime_checkable
class AsrAdapter(Protocol):
    def transcribe(
        self,
        audio: bytes,
        *,
        language: str = "en",
        audio_format: str | None = "pcm_s16le",
    ) -> str: ...


@runtime_checkable
class TtsAdapter(Protocol):
    def tts_url_for(self, text: str) -> str: ...


@runtime_checkable
class LlmAdapter(Protocol):
    def chat(self, system: str, messages: list[dict[str, str]]) -> str: ...


@runtime_checkable
class KnowledgeRetriever(Protocol):
    def retrieve(self, query: str, *, filters: dict[str, Any], top_k: int) -> list[dict[str, Any]]: ...
