from __future__ import annotations

import json
import re
from typing import Any

from Vocabulary_model.reinforce_quiz.llm_client import try_chat
from Vocabulary_model.study_words_cli import Entry, extract_chinese_meaning

_WORD_RE = re.compile(r"[A-Za-z]+")


def _meaning(entry: Entry) -> str:
    g = (entry.gloss1 or "").strip()
    return g or extract_chinese_meaning(entry.content)


def _cloze_from_example(entry: Entry) -> dict[str, Any] | None:
    example = (entry.example_phrase or "").strip()
    if not example:
        return None
    pattern = re.compile(re.escape(entry.word), re.IGNORECASE)
    if not pattern.search(example):
        return None
    blanked = pattern.sub("_____", example, count=1)
    return {
        "type": "cloze",
        "prompt": f"请填写正确的单词（{entry.word}）",
        "word": entry.word,
        "sentence": blanked,
        "answer": entry.word,
        "accept": [entry.word, entry.word.lower(), entry.word.capitalize()],
        "source": "wordbook",
    }


def _cloze_from_llm(entry: Entry) -> dict[str, Any]:
    meaning = _meaning(entry)
    system = (
        "你是英语练习题助手。只输出 JSON，不要 markdown。"
        '格式：{"sentence":"英文例句，用_____表示空格","answer":"目标词原形"}'
    )
    user = (
        f"为单词 {entry.word}（释义：{meaning}）写一句中等难度英文例句，"
        f"将 {entry.word} 替换为 _____。"
    )
    raw = try_chat(system, user, max_tokens=180)
    if raw:
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            data = json.loads(text)
            sentence = str(data.get("sentence") or "").strip()
            answer = str(data.get("answer") or entry.word).strip()
            if sentence and "_____" in sentence:
                return {
                    "type": "cloze",
                    "prompt": f"请填写正确的单词（{entry.word}）",
                    "word": entry.word,
                    "sentence": sentence,
                    "answer": answer,
                    "accept": list(
                        {answer, answer.lower(), answer.capitalize(), entry.word}
                    ),
                    "source": "llm",
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return {
        "type": "cloze",
        "prompt": f"请填写正确的单词",
        "word": entry.word,
        "sentence": f"The word _____ means {_meaning(entry)[:40]}.",
        "answer": entry.word,
        "accept": [entry.word, entry.word.lower(), entry.word.capitalize()],
        "source": "fallback",
    }


def build_cloze(entry: Entry) -> dict[str, Any]:
    from_wb = _cloze_from_example(entry)
    if from_wb is not None:
        return from_wb
    return _cloze_from_llm(entry)
