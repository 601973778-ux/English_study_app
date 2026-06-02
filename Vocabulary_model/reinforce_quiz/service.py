from __future__ import annotations

import secrets
from typing import Any

from Vocabulary_model.reinforce_quiz.cloze_generator import build_cloze
from Vocabulary_model.reinforce_quiz.llm_client import try_chat
from Vocabulary_model.reinforce_quiz.mcq_generator import build_mcq
from Vocabulary_model.study_words_cli import Entry, extract_chinese_meaning

# quiz_id -> answer payload (server process memory, tied to session lifecycle)
_PENDING: dict[str, dict[str, Any]] = {}


def _meaning(entry: Entry) -> str:
    g = (entry.gloss1 or "").strip()
    return g or extract_chinese_meaning(entry.content)


def generate_quiz(
    *,
    entry: Entry,
    stage: int,
    variant: int,
    entries: list[Entry],
    wordbook_id: str,
) -> dict[str, Any]:
    if stage == 2:
        quiz = build_mcq(entry, entries, wordbook_id=wordbook_id, variant=variant)
    elif stage == 3:
        quiz = build_cloze(entry)
    else:
        raise ValueError("stage 须为 2 或 3")

    quiz_id = secrets.token_urlsafe(12)
    public = {
        "quiz_id": quiz_id,
        "type": quiz["type"],
        "prompt": quiz["prompt"],
        "word": quiz["word"],
        "stage": stage,
        "variant": variant,
    }
    if quiz["type"] == "mcq":
        public["options"] = list(quiz["options"])
        _PENDING[quiz_id] = {
            "stage": 2,
            "word": entry.word,
            "correct_index": int(quiz["correct_index"]),
            "options_meta": quiz["options_meta"],
            "correct_meaning": _meaning(entry),
        }
    else:
        public["sentence"] = quiz["sentence"]
        _PENDING[quiz_id] = {
            "stage": 3,
            "word": entry.word,
            "answer": str(quiz["answer"]).strip(),
            "accept": [str(a).strip() for a in quiz.get("accept") or []],
            "correct_meaning": _meaning(entry),
        }
    public["source"] = quiz.get("source", "generated")
    return public


def _explain_mcq_wrong(pending: dict[str, Any], selected_index: int) -> str:
    meta = pending.get("options_meta") or []
    if not isinstance(meta, list) or selected_index >= len(meta):
        return "答案不正确，请再试一次。"
    chosen = meta[selected_index]
    correct_word = pending.get("word", "")
    correct_meaning = pending.get("correct_meaning", "")
    chosen_word = str(chosen.get("word") or "")
    chosen_text = str(chosen.get("text") or "")
    system = "你是英语词汇教练。用 1–3 句简洁中文解释混淆点，并给出区分记忆提示。不要 markdown。"
    user = (
        f"目标词：{correct_word}（{correct_meaning}）。"
        f"学习者错选了 {chosen_word}（{chosen_text}）。"
        f"请说明为什么容易选错，以及如何区分这两个词。"
    )
    llm_text = try_chat(system, user, max_tokens=220)
    if llm_text:
        return llm_text.strip()
    return (
        f"不正确。{correct_word} 的释义是「{correct_meaning}」，"
        f"而 {chosen_word} 表示「{chosen_text}」。"
    )


def _normalize_answer(text: str) -> str:
    return str(text or "").strip().casefold()


def grade_quiz(*, quiz_id: str, answer: Any) -> dict[str, Any]:
    pending = _PENDING.pop(quiz_id, None)
    if not pending:
        raise ValueError("测验已失效，请重新生成题目")

    stage = int(pending.get("stage") or 0)
    word = str(pending.get("word") or "")

    if stage == 2:
        try:
            selected = int(answer)
        except (TypeError, ValueError):
            raise ValueError("请选择一个选项") from None
        correct_index = int(pending["correct_index"])
        correct = selected == correct_index
        feedback = (
            "回答正确！"
            if correct
            else _explain_mcq_wrong(pending, selected)
        )
        return {
            "correct": correct,
            "stage": 2,
            "word": word,
            "feedback": feedback,
            "graduated": False,
            "next_stage": 3 if correct else 2,
            "advance_variant": not correct,
        }

    if stage == 3:
        text = str(answer or "").strip()
        if not text:
            raise ValueError("请填写答案")
        accept = {_normalize_answer(a) for a in (pending.get("accept") or [])}
        accept.add(_normalize_answer(pending.get("answer", "")))
        correct = _normalize_answer(text) in accept
        feedback = (
            "填空正确，该词巩固完成！"
            if correct
            else f"不正确。提示：与「{pending.get('correct_meaning', '')}」相关的词是 {word}。"
        )
        return {
            "correct": correct,
            "stage": 3,
            "word": word,
            "feedback": feedback,
            "graduated": correct,
            "next_stage": 3 if not correct else None,
            "advance_variant": False,
        }

    raise ValueError("未知测验类型")


def clear_pending_for_word(word: str) -> None:
    w = str(word).strip().casefold()
    dead = [k for k, v in _PENDING.items() if str(v.get("word", "")).casefold() == w]
    for k in dead:
        _PENDING.pop(k, None)
