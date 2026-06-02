from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from Spoken_model.dialogue.contracts.protocols import ScenarioPlugin
from Spoken_model.dialogue.contracts.types import RouteKind, SessionState
from Spoken_model.dialogue.core.text_normalizer import normalize_user_text, token_set

_QUESTION_TOKENS = frozenset(
    {"what", "which", "how", "why", "when", "where", "who", "whose", "whom"}
)
_ORDER_SLOT_RULES = frozenset({"drink", "order_food", "party_size"})
_ORDER_INTENT_TOKENS = frozenset(
    {"like", "have", "get", "take", "order", "want", "need", "i'll", "i'd"}
)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _looks_like_question(text: str, tokens: set[str]) -> bool:
    lowered = text.lower()
    if "?" in lowered:
        return True
    if tokens & _QUESTION_TOKENS:
        return True
    if "kind" in tokens and ("of" in tokens or "what" in tokens):
        return True
    return False


def _skip_order_slot_on_question(rule_id: str, is_question: bool, tokens: set[str]) -> bool:
    if not is_question or rule_id not in _ORDER_SLOT_RULES:
        return False
    return not bool(tokens & _ORDER_INTENT_TOKENS)


def _normalize_terms(items: list[str] | None) -> set[str]:
    return {str(x).strip().lower() for x in (items or []) if str(x).strip()}


def _match_patterns(text: str, patterns: list[str]) -> bool:
    lowered = normalize_user_text(text).lower()
    tokens = token_set(text)
    for pat in patterns:
        p = pat.strip().lower()
        if not p:
            continue
        if p.startswith("re:"):
            if re.search(p[3:], lowered):
                return True
        elif " " in p:
            if p in lowered:
                return True
        elif p in tokens:
            return True
    return False


def _rule_matches(text: str, rule: dict[str, Any], tokens: set[str]) -> bool:
    if not _match_patterns(text, rule.get("patterns") or []):
        return False
    requires = _normalize_terms(rule.get("requires_any"))
    if requires and not (tokens & requires):
        return False
    excludes = _normalize_terms(rule.get("excludes_any"))
    if excludes and (tokens & excludes):
        return False
    return True


class JsonScenarioPlugin:
    """Load scenario pack from JSON files under a scenario directory."""

    def __init__(self, scenario_dir: Path, *, default_dir: Path | None = None) -> None:
        self._dir = scenario_dir
        manifest = _load_json(scenario_dir / "manifest.json") or {}
        scenario = _load_json(scenario_dir / "scenario.json") or {}
        self.scenario_id = str(manifest.get("id") or scenario_dir.name)
        self.title_zh = str(manifest.get("title_zh") or scenario.get("title_zh") or self.scenario_id)
        self.title_en = str(manifest.get("title_en") or scenario.get("title_en") or self.scenario_id)
        self._opening = str(scenario.get("opening_line") or "Hello! How can I help you today?")
        self._opening_mode = str(scenario.get("opening_mode") or "static").strip().lower()
        self._opening_rag_query = str(
            scenario.get("opening_rag_query")
            or "waiter greeting welcome restaurant table reservation"
        )
        raw_fallback = scenario.get("opening_fallback_lines")
        if isinstance(raw_fallback, list) and raw_fallback:
            self._opening_fallback_lines = [str(x).strip() for x in raw_fallback if str(x).strip()]
        else:
            self._opening_fallback_lines = [self._opening]
        self._opening_rag_filter = (
            _load_json(scenario_dir / "opening_rag_filter.json")
            or scenario.get("opening_rag_filter")
            or {}
        )
        self._default_stage = str(scenario.get("default_stage") or "GREETING")
        self._cycle_size = int(scenario.get("cycle_size") or 10)
        self._topic_keywords = set(str(k).lower() for k in scenario.get("topic_keywords") or [])
        self._rag_filter = _load_json(scenario_dir / "rag_filter.json") or {}
        self._coverage = _load_json(scenario_dir / "coverage.json") or {}
        self._scripts = self._merge_scripts(scenario_dir, default_dir)
        self._redirects = self._scripts.get("redirect") or []
        self._control = self._scripts.get("control") or []
        self._chitchat = self._scripts.get("chitchat") or []
        self._topic = self._scripts.get("topic") or []

    @property
    def cycle_size(self) -> int:
        return self._cycle_size

    @property
    def default_stage(self) -> str:
        return self._default_stage

    def _merge_scripts(self, scenario_dir: Path, default_dir: Path | None) -> dict[str, list[dict[str, Any]]]:
        merged: dict[str, list[dict[str, Any]]] = {
            "control": [],
            "chitchat": [],
            "topic": [],
            "redirect": [],
        }
        if default_dir and default_dir.is_dir():
            for key in merged:
                data = _load_json(default_dir / f"{key}.json")
                if isinstance(data, list):
                    merged[key].extend(data)
        scripts_dir = scenario_dir / "scripts"
        if scripts_dir.is_dir():
            for key in merged:
                data = _load_json(scripts_dir / f"{key}.json")
                if isinstance(data, list):
                    merged[key].extend(data)
        return merged

    def opening_line(self, session: SessionState) -> str:
        return self._opening

    @property
    def opening_mode(self) -> str:
        return self._opening_mode

    def opening_rag_query(self, session: SessionState) -> str:
        return self._opening_rag_query

    def opening_rag_filters(self) -> dict[str, Any]:
        return dict(self._opening_rag_filter)

    def opening_fallback_line(self, session: SessionState) -> str:
        del session
        return random.choice(self._opening_fallback_lines)

    def opening_llm_system_prompt(self, session: SessionState) -> str:
        return (
            f"You are a friendly English-speaking waiter in a restaurant scenario. "
            f"Current stage: {session.stage}. "
            f"Reply in 1-2 short sentences only. Stay in character. English only."
        )

    def classify(self, user_text: str, session: SessionState) -> RouteKind:
        text = normalize_user_text(user_text)
        if not text:
            return RouteKind.SCRIPT_CONTROL
        for rule in self._control:
            if _match_patterns(text, rule.get("patterns") or []):
                return RouteKind.SCRIPT_CONTROL
        for rule in self._redirects:
            if _match_patterns(text, rule.get("patterns") or []):
                return RouteKind.REDIRECT
        for rule in self._chitchat:
            if _match_patterns(text, rule.get("patterns") or []):
                return RouteKind.SCRIPT_CHITCHAT
        tokens = token_set(text)
        is_question = _looks_like_question(text, tokens)
        if self._topic_keywords and not is_question and tokens & self._topic_keywords:
            return RouteKind.SCRIPT_TOPIC
        for rule in self._topic:
            rule_id = str(rule.get("id") or "")
            if _skip_order_slot_on_question(rule_id, is_question, tokens):
                continue
            if _rule_matches(text, rule, tokens):
                return RouteKind.SCRIPT_TOPIC
        return RouteKind.RAG_LLM

    def try_script(
        self, user_text: str, session: SessionState, route: RouteKind
    ) -> tuple[str | None, str | None]:
        pool: list[dict[str, Any]]
        if route == RouteKind.SCRIPT_CONTROL:
            pool = self._control
        elif route == RouteKind.SCRIPT_CHITCHAT:
            pool = self._chitchat
        elif route == RouteKind.SCRIPT_TOPIC:
            pool = self._topic
        elif route == RouteKind.REDIRECT:
            pool = self._redirects
        else:
            return None, None

        text = normalize_user_text(user_text)
        tokens = token_set(text)
        is_question = _looks_like_question(text, tokens)
        for rule in pool:
            rule_id = str(rule.get("id") or "")
            if _skip_order_slot_on_question(rule_id, is_question, tokens):
                continue
            if not _rule_matches(text, rule, tokens):
                continue
            reply = str(rule.get("reply") or rule.get("replies", [""])[0])
            next_stage = rule.get("next_stage")
            slots = rule.get("set_slots") or {}
            for k, v in slots.items():
                session.slots[k] = v
            if rule.get("extract_party_size"):
                m = re.search(r"\b(one|two|three|four|five|six|\d+)\b", text.lower())
                if m:
                    session.slots["party_size"] = m.group(1)
            return reply, str(next_stage) if next_stage else None
        return None, None

    def on_turn_end(
        self, user_text: str, reply: str, session: SessionState, route: RouteKind
    ) -> SessionState:
        session.transcript.append(
            {
                "user": user_text,
                "assistant": reply,
                "route": route.value,
                "stage": session.stage,
            }
        )
        return session

    def rag_query(self, user_text: str, session: SessionState) -> str:
        parts = [user_text, session.stage]
        if session.slots:
            parts.append(" ".join(str(v) for v in session.slots.values()))
        return " ".join(p for p in parts if p)

    def rag_filters(self) -> dict[str, Any]:
        return dict(self._rag_filter)

    def llm_system_prompt(self, session: SessionState) -> str:
        return (
            f"You are a friendly English-speaking waiter in a restaurant scenario. "
            f"Current stage: {session.stage}. "
            f"Reply in 1-3 short sentences. Stay in character."
        )

    def coverage_checklist(self) -> list[dict[str, Any]]:
        items = self._coverage.get("items") if isinstance(self._coverage, dict) else None
        return list(items or [])

    def topic_keywords(self) -> set[str]:
        return set(self._topic_keywords)


def load_scenario(scenario_dir: Path, *, default_dir: Path | None = None) -> JsonScenarioPlugin:
    return JsonScenarioPlugin(scenario_dir, default_dir=default_dir)
