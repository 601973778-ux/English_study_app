from __future__ import annotations

import random
import re
from typing import Any

from Vocabulary_model.similar_neighbors_service import similar_words_payload
from Vocabulary_model.study_words_cli import Entry, extract_chinese_meaning

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def _meaning_text(entry: Entry) -> str:
    g = (entry.gloss1 or "").strip()
    if g:
        return g
    return extract_chinese_meaning(entry.content)


def _gloss_overlap(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    chars_a = {c for c in a if CHINESE_RE.match(c)}
    chars_b = {c for c in b if CHINESE_RE.match(c)}
    return len(chars_a & chars_b) >= 2


def _entry_by_word(entries: list[Entry]) -> dict[str, Entry]:
    out: dict[str, Entry] = {}
    for e in entries:
        out[e.word] = e
        k = e.word.casefold()
        if k not in {x.casefold() for x in out}:
            pass
    return {e.word: e for e in entries}


def _cf_map(entries: list[Entry]) -> dict[str, Entry]:
    m: dict[str, Entry] = {}
    for e in entries:
        k = e.word.casefold()
        if k not in m:
            m[k] = e
    return m


def pick_distractor_entries(
    target: Entry,
    entries: list[Entry],
    *,
    wordbook_id: str,
    variant: int,
    need: int = 3,
) -> list[Entry]:
    by_cf = _cf_map(entries)
    pool_words: list[str] = []

    sim = similar_words_payload(target.word, wordbook_id)
    for item in sim.get("items") or []:
        w = str(item.get("word") or "").strip()
        if w and w.casefold() != target.word.casefold():
            pool_words.append(w)

    target_meaning = _meaning_text(target)
    for e in entries:
        if e.word.casefold() == target.word.casefold():
            continue
        if _gloss_overlap(target_meaning, _meaning_text(e)):
            pool_words.append(e.word)

    seen: set[str] = {target.word.casefold()}
    ordered: list[str] = []
    for w in pool_words:
        k = w.casefold()
        if k in seen:
            continue
        seen.add(k)
        ordered.append(w)

    rng = random.Random(f"{target.word}:{wordbook_id}:{variant}")
    rng.shuffle(ordered)

    picked: list[Entry] = []
    for w in ordered:
        e = by_cf.get(w.casefold()) or _entry_by_word(entries).get(w)
        if e is None:
            e = by_cf.get(w.casefold())
        if e is None:
            continue
        if e.word.casefold() == target.word.casefold():
            continue
        picked.append(e)
        if len(picked) >= need:
            break

    if len(picked) < need:
        candidates = [e for e in entries if e.word.casefold() != target.word.casefold()]
        rng.shuffle(candidates)
        for e in candidates:
            if any(e.word.casefold() == p.word.casefold() for p in picked):
                continue
            picked.append(e)
            if len(picked) >= need:
                break

    return picked[:need]


def build_word_mcq(
    target: Entry,
    entries: list[Entry],
    *,
    wordbook_id: str,
    variant: int,
) -> dict[str, Any]:
    """阶段 3：给释义，四选一英文单词。"""
    meaning = _meaning_text(target)
    distractors = pick_distractor_entries(
        target,
        entries,
        wordbook_id=wordbook_id,
        variant=variant + 1000,
        need=3,
    )
    options_meta = [{"word": target.word, "text": target.word, "is_correct": True}]
    for d in distractors:
        options_meta.append(
            {"word": d.word, "text": d.word, "is_correct": False}
        )

    rng = random.Random(f"word-mcq-shuffle:{target.word}:{variant}")
    rng.shuffle(options_meta)

    options = [m["text"] for m in options_meta]
    correct_index = next(i for i, m in enumerate(options_meta) if m["is_correct"])

    return {
        "type": "word_mcq",
        "prompt": f"释义「{meaning}」对应的单词是？",
        "word": target.word,
        "options": options,
        "correct_index": correct_index,
        "options_meta": options_meta,
    }


def build_mcq(
    target: Entry,
    entries: list[Entry],
    *,
    wordbook_id: str,
    variant: int,
) -> dict[str, Any]:
    correct = _meaning_text(target)
    distractors = pick_distractor_entries(
        target, entries, wordbook_id=wordbook_id, variant=variant, need=3
    )
    options_meta = [{"word": target.word, "text": correct, "is_correct": True}]
    for d in distractors:
        options_meta.append(
            {"word": d.word, "text": _meaning_text(d), "is_correct": False}
        )

    rng = random.Random(f"mcq-shuffle:{target.word}:{variant}")
    rng.shuffle(options_meta)

    options = [m["text"] for m in options_meta]
    correct_index = next(i for i, m in enumerate(options_meta) if m["is_correct"])
    distractor_words = [m["word"] for m in options_meta if not m["is_correct"]]

    return {
        "type": "mcq",
        "prompt": f"请选择「{target.word}」的正确释义",
        "word": target.word,
        "options": options,
        "correct_index": correct_index,
        "distractor_words": distractor_words,
        "options_meta": options_meta,
    }
