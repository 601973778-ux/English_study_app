from __future__ import annotations

import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from Vocabulary_model.placement.mcq import build_placement_mcq, grade_mcq
from Vocabulary_model.placement.planner import (
    adjust_cursor_after_main,
    cursor_after_probe,
    estimate_candidate_band,
    plan_adjacent,
    plan_confirm,
    plan_main,
    plan_probe,
)
from Vocabulary_model.placement.scoring import compute_result
from Vocabulary_model.placement.wordbank import (
    BAND_LABEL,
    PlacementWord,
    load_wordbank,
    words_by_band,
)

_SESSIONS: dict[str, "PlacementSession"] = {}
_WORDS: list[PlacementWord] | None = None
TOTAL_QUESTIONS = 10


@dataclass
class PlacementSession:
    placement_id: str
    seed: int
    rng: random.Random
    buckets: dict[str, list[PlacementWord]]
    all_words: list[PlacementWord]
    queue: list[PlacementWord] = field(default_factory=list)
    answers: list[dict[str, Any]] = field(default_factory=list)
    cursor_level: int = 2
    phase: str = "probe"
    created_at: float = field(default_factory=time.time)

    @property
    def index(self) -> int:
        return len(self.answers)

    @property
    def finished(self) -> bool:
        return self.index >= TOTAL_QUESTIONS

    def _used(self) -> set[str]:
        used = {w.word.casefold() for w in self.queue}
        used.update(str(a.get("word", "")).casefold() for a in self.answers)
        return used

    def current_word(self) -> PlacementWord | None:
        if self.index >= len(self.queue):
            return None
        return self.queue[self.index]

    def extend_queue(self, words: list[PlacementWord]) -> None:
        self.queue.extend(words)

    def probe_correct(self) -> int:
        return sum(
            1 for a in self.answers
            if a.get("phase") == "probe" and a.get("correct")
        )

    def main_correct(self) -> int:
        return sum(
            1 for a in self.answers
            if a.get("phase") == "main" and a.get("correct")
        )

    def after_probe(self) -> None:
        self.cursor_level = cursor_after_probe(self.probe_correct())
        main_words = plan_main(self.cursor_level, self.rng, self.buckets, self._used())
        self.extend_queue(main_words)
        self.phase = "main"

    def after_main(self) -> None:
        mc = self.main_correct()
        self.cursor_level = adjust_cursor_after_main(self.cursor_level, mc)
        adj = plan_adjacent(self.cursor_level, mc, self.rng, self.buckets, self._used())
        self.extend_queue(adj)
        self.phase = "adjacent"

    def after_adjacent(self) -> None:
        candidate = estimate_candidate_band(self.answers)
        confirm = plan_confirm(candidate, self.rng, self.buckets, self._used())
        self.extend_queue(confirm)
        self.phase = "confirm"


def _get_words() -> list[PlacementWord]:
    global _WORDS
    if _WORDS is None:
        _WORDS = load_wordbank()
    return _WORDS


def _phase_for_index(session: PlacementSession, index: int) -> str:
    if index < 2:
        return "probe"
    if index < 5:
        return "main"
    if index < 7:
        return "adjacent"
    return "confirm"


def _ensure_queue(session: PlacementSession) -> None:
    while session.index >= len(session.queue) and not session.finished:
        if session.phase == "probe" and session.index >= 2:
            session.after_probe()
        elif session.phase == "main" and session.index >= 5:
            session.after_main()
        elif session.phase == "adjacent" and session.index >= 7:
            session.after_adjacent()
        else:
            break


def start_placement(*, seed: int | None = None) -> dict[str, Any]:
    all_words = _get_words()
    if not all_words:
        raise ValueError("评估词库为空")
    sid = secrets.token_urlsafe(10)
    s = seed if seed is not None else int(time.time()) % 1_000_000_000
    rng = random.Random(s)
    buckets = words_by_band(all_words)
    if len(buckets.get("cet6", [])) < 2:
        raise ValueError("六级评估词不足，请检查 placement_assessment_words.json")

    session = PlacementSession(
        placement_id=sid,
        seed=s,
        rng=rng,
        buckets=buckets,
        all_words=all_words,
        queue=plan_probe(rng, buckets, set()),
    )
    _SESSIONS[sid] = session

    word = session.current_word()
    if word is None:
        raise ValueError("无法生成评估题目")
    quiz = build_placement_mcq(word, all_words, seed=session.seed + session.index)

    return {
        "placement_id": sid,
        "index": 0,
        "total": TOTAL_QUESTIONS,
        "phase": session.phase,
        "quiz": quiz,
    }


def submit_answer(*, placement_id: str, quiz_id: str, answer: Any) -> dict[str, Any]:
    session = _SESSIONS.get(placement_id)
    if session is None:
        raise ValueError("评估已失效，请重新开始")

    word = session.current_word()
    if word is None:
        raise ValueError("没有待答题目")

    correct, feedback = grade_mcq(quiz_id, answer)
    phase = _phase_for_index(session, session.index)
    session.answers.append(
        {
            "word": word.word,
            "meaning": word.meaning,
            "source": word.source,
            "band": word.band,
            "level": word.level,
            "phase": phase,
            "correct": correct,
        }
    )

    if session.finished:
        result = compute_result(session.answers)
        _SESSIONS.pop(placement_id, None)
        return {
            "finished": True,
            "correct": correct,
            "feedback": feedback,
            "index": session.index,
            "total": TOTAL_QUESTIONS,
            "result": result,
        }

    _ensure_queue(session)
    next_word = session.current_word()
    if next_word is None:
        raise ValueError("题目队列异常，请重新开始评估")

    quiz = build_placement_mcq(next_word, session.all_words, seed=session.seed + session.index)
    return {
        "finished": False,
        "correct": correct,
        "feedback": feedback,
        "index": session.index,
        "total": TOTAL_QUESTIONS,
        "phase": _phase_for_index(session, session.index),
        "quiz": quiz,
    }


def grade_answer(quiz_id: str, answer: Any) -> tuple[bool, str]:
    return grade_mcq(quiz_id, answer)


def apply_recommendation_to_settings(settings: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    out = dict(settings)
    out["wordbook_id"] = str(result.get("recommend_wordbook_id") or out.get("wordbook_id", "cet6"))
    out["daily_words"] = int(result.get("recommend_daily_words") or out.get("daily_words", 50))
    out["placement_band"] = str(result.get("mastered_band") or "")
    out["placement_label"] = str(result.get("level_label") or "")
    out["placement_percent"] = int(result.get("percent") or 0)
    out["placement_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    wid = out["wordbook_id"]
    out["wordbook_label"] = BAND_LABEL.get(wid, wid)
    return out
