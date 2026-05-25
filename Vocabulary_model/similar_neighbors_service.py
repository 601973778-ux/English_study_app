"""
形近词：按当前词书加载对应 *_similar_shape_words.json，释义仅展示词条的「释义1」。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from Vocabulary_model.study_words_cli import Entry, extract_chinese_meaning
    from Vocabulary_model.wordbook_catalog import (
        DEFAULT_WORDBOOK_ID,
        normalize_wordbook_id,
        resolve_wordbook_path,
        similar_index_path,
    )
    from Vocabulary_model.similar_shape_word import build_similar_index_for_path
except ModuleNotFoundError:  # pragma: no cover
    from study_words_cli import Entry, extract_chinese_meaning
    from wordbook_catalog import (
        DEFAULT_WORDBOOK_ID,
        normalize_wordbook_id,
        resolve_wordbook_path,
        similar_index_path,
    )
    from similar_shape_word import build_similar_index_for_path

_by_wordbook: dict[str, tuple[dict[str, list[str]], dict[str, str]]] = {}
_active_wordbook_id: str = DEFAULT_WORDBOOK_ID

_entry_by_word: dict[str, Entry] | None = None
_entry_by_cf: dict[str, Entry] | None = None

MAX_NEIGHBORS = 24


def set_similar_wordbook(wordbook_id: str) -> None:
    global _active_wordbook_id
    _active_wordbook_id = normalize_wordbook_id(wordbook_id)


def invalidate_similar_cache(wordbook_id: str | None = None) -> None:
    if wordbook_id is None:
        _by_wordbook.clear()
        return
    _by_wordbook.pop(normalize_wordbook_id(wordbook_id), None)


def _load_similar_maps(wordbook_id: str) -> tuple[dict[str, list[str]], dict[str, str]]:
    wid = normalize_wordbook_id(wordbook_id)
    if wid in _by_wordbook:
        return _by_wordbook[wid]

    index_path = similar_index_path(wid)
    if not index_path.is_file():
        wordbook_json = resolve_wordbook_path(wid)
        if wordbook_json.is_file():
            try:
                build_similar_index_for_path(wordbook_json, index_path)
            except (OSError, ValueError):
                pass

    by_word: dict[str, list[str]] = {}
    cf_to_canonical: dict[str, str] = {}
    if index_path.is_file():
        raw = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                w = item.get("word")
                if not isinstance(w, str) or not w.strip():
                    continue
                nbs = item.get("neighbors")
                neighbors: list[str] = []
                if isinstance(nbs, list):
                    for x in nbs:
                        if isinstance(x, str) and x.strip():
                            neighbors.append(x.strip())
                by_word[w] = neighbors
                cf = w.casefold()
                if cf not in cf_to_canonical:
                    cf_to_canonical[cf] = w.strip()

    _by_wordbook[wid] = (by_word, cf_to_canonical)
    return by_word, cf_to_canonical


def _neighbors_for_head(head: str, wordbook_id: str) -> tuple[str | None, list[str]]:
    by_word, cf_map = _load_similar_maps(wordbook_id)
    h = head.strip()
    if not h:
        return None, []
    if h in by_word:
        return h, list(by_word[h])
    canon = cf_map.get(h.casefold())
    if canon is not None and canon in by_word:
        return canon, list(by_word[canon])
    return None, []


def set_entry_cache(entries: list[Entry]) -> None:
    global _entry_by_word, _entry_by_cf
    _entry_by_word = {}
    _entry_by_cf = {}
    for e in entries:
        _entry_by_word[e.word] = e
        k = e.word.casefold()
        if k not in _entry_by_cf:
            _entry_by_cf[k] = e


def _meaning_for_neighbor(neighbor: str) -> str:
    if _entry_by_word is None or _entry_by_cf is None:
        return "（词库未加载）"
    e = _entry_by_word.get(neighbor)
    if e is None:
        e = _entry_by_cf.get(neighbor.casefold())
    if e is None:
        return "（词库暂无该词释义）"
    gloss1 = (e.gloss1 or "").strip()
    if gloss1:
        return gloss1
    return extract_chinese_meaning(e.content)


def similar_words_payload(head_word: str, wordbook_id: str | None = None) -> dict[str, Any]:
    """
    JSON-serializable payload for GET /api/similar-for?word=...

  - items: { word, meaning } — meaning 为当前词书中的「释义1」。
    """
    wid = normalize_wordbook_id(wordbook_id or _active_wordbook_id)
    canonical, neighbors = _neighbors_for_head(head_word, wid)
    index_miss = canonical is None and bool(head_word.strip())

    if canonical is None:
        display_head = head_word.strip() or head_word
        return {
            "word": display_head,
            "items": [],
            "index_miss": index_miss,
            "truncated": False,
            "wordbook_id": wid,
        }

    truncated = len(neighbors) > MAX_NEIGHBORS
    slice_n = neighbors[:MAX_NEIGHBORS]
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for nb in slice_n:
        key_cf = nb.casefold()
        if key_cf in seen:
            continue
        seen.add(key_cf)
        items.append({"word": nb, "meaning": _meaning_for_neighbor(nb)})

    return {
        "word": canonical,
        "items": items,
        "index_miss": False,
        "truncated": truncated,
        "wordbook_id": wid,
    }
