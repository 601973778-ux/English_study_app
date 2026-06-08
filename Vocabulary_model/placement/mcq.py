from __future__ import annotations

import json
import random
import re
import secrets
from typing import Any

from Vocabulary_model.placement.wordbank import PlacementWord
from Vocabulary_model.reinforce_quiz.llm_client import try_chat

_PENDING: dict[str, dict[str, Any]] = {}


def _same_meaning(a: str, b: str) -> bool:
    return str(a or "").strip() == str(b or "").strip()


def _parse_json_payload(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _llm_similar_meaning_distractor(target: PlacementWord) -> str | None:
    """由大模型生成形近词，并返回该形近词的中文释义（作唯一易混淆项）。"""
    system = (
        "你是英语词汇专家。只输出 JSON，不要 markdown。\n"
        '格式：{"similar_word":"英文形近词","meaning":"该形近词的中文释义"}\n'
        "要求：\n"
        "1. similar_word 与目标词拼写形近、易混淆，但不能是目标词本身\n"
        "2. meaning 必须是 similar_word 的常见中文释义，且不得与目标词释义相同\n"
        "3. 只输出一个最佳形近词"
    )
    user = (
        f"目标词：{target.word}\n"
        f"目标词释义：{target.meaning}\n"
        "请给出一个形近词及其中文释义。"
    )
    raw = try_chat(system, user, max_tokens=180)
    if not raw:
        return None
    try:
        data = _parse_json_payload(raw)
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None
        similar_word = str(data.get("similar_word") or data.get("word") or "").strip()
        meaning = str(data.get("meaning") or data.get("text") or "").strip()
        if not similar_word or not meaning:
            return None
        if similar_word.casefold() == target.word.casefold():
            return None
        if _same_meaning(meaning, target.meaning):
            return None
        return meaning
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _plain_distractor(
    target: PlacementWord,
    all_words: list[PlacementWord],
    rng: random.Random,
    *,
    exclude: set[str],
) -> str:
    same_band = [
        w for w in all_words
        if w.band == target.band
        and w.word.casefold() != target.word.casefold()
        and not _same_meaning(w.meaning, target.meaning)
        and w.meaning not in exclude
    ]
    pool = same_band or [
        w for w in all_words
        if w.word.casefold() != target.word.casefold()
        and not _same_meaning(w.meaning, target.meaning)
        and w.meaning not in exclude
    ]
    if not pool:
        return "（无相关释义）"
    return rng.choice(pool).meaning


def build_placement_mcq(
    target: PlacementWord,
    all_words: list[PlacementWord],
    *,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{target.word}:{target.band}")

    similar_meaning = _llm_similar_meaning_distractor(target)

    exclude: set[str] = {target.meaning}
    if similar_meaning:
        exclude.add(similar_meaning)

    options: list[str] = [target.meaning]
    if similar_meaning:
        options.append(similar_meaning)

    while len(options) < 4:
        filler = _plain_distractor(target, all_words, rng, exclude=exclude)
        if filler not in exclude:
            options.append(filler)
            exclude.add(filler)

    rng.shuffle(options)
    correct_index = options.index(target.meaning)

    quiz_id = secrets.token_urlsafe(12)
    _PENDING[quiz_id] = {
        "word": target.word,
        "correct_index": correct_index,
        "correct_meaning": target.meaning,
    }

    return {
        "quiz_id": quiz_id,
        "type": "placement_mcq",
        "prompt": f"请选择「{target.word}」的正确释义",
        "word": target.word,
        "source": target.source,
        "band": target.band,
        "level": target.level,
        "options": options,
    }


def grade_mcq(quiz_id: str, answer: Any) -> tuple[bool, str]:
    pending = _PENDING.pop(quiz_id, None)
    if not pending:
        raise ValueError("题目已失效，请重新开始评估")
    try:
        selected = int(answer)
    except (TypeError, ValueError):
        raise ValueError("请选择一个选项") from None
    correct_index = int(pending["correct_index"])
    correct = selected == correct_index
    if correct:
        return True, "回答正确"
    return False, "回答不正确"
