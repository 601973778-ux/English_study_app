"""
用户已学单词：JSON 文件持久化（按词书分桶）。

默认路径：Vocabulary_model/user_data/learned_words.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from Vocabulary_model.json_file_io import save_json_atomic
from Vocabulary_model.wordbook_catalog import DEFAULT_WORDBOOK_ID, normalize_wordbook_id

DATA_DIR = Path(__file__).resolve().parent / "user_data"
LEARNED_WORDS_FILE = DATA_DIR / "learned_words.json"
FILE_VERSION = 1

SELF_RATING_WINDOW_SIZE = 3
VALID_SELF_RATING_CHOICES = frozenset({"k", "u"})


def _empty_self_rating_window() -> dict[str, Any]:
    return {
        "recent": [],
        "known_count": 0,
        "unknown_count": 0,
        "window_size": SELF_RATING_WINDOW_SIZE,
        "window_full": False,
    }


def _push_self_rating_window(window: dict[str, Any], choice: str) -> None:
    if choice not in VALID_SELF_RATING_CHOICES:
        raise ValueError("choice must be k or u")
    size = SELF_RATING_WINDOW_SIZE
    recent = list(window.get("recent") or [])
    if len(recent) > size:
        recent = recent[-size:]
    known = sum(1 for x in recent if x == "k")
    unknown = sum(1 for x in recent if x == "u")

    recent.append(choice)
    if choice == "k":
        known += 1
    else:
        unknown += 1

    while len(recent) > size:
        dropped = recent.pop(0)
        if dropped == "k":
            known -= 1
        else:
            unknown -= 1

    window["recent"] = recent
    window["known_count"] = known
    window["unknown_count"] = unknown
    window["window_size"] = size
    window["window_full"] = len(recent) >= size
    if window["window_full"]:
        window["known_ratio"] = round(known / size, 4)
    else:
        window.pop("known_ratio", None)


def _new_word_row(word: str, *, now: str | None = None) -> dict[str, Any]:
    ts = now or _utc_now_iso()
    return {
        "word": word,
        "first_learned_at": ts,
        "last_seen_at": ts,
        "total_seen": 0,
        "self_rating_window": _empty_self_rating_window(),
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_root() -> dict[str, Any]:
    return {"version": FILE_VERSION, "wordbooks": {}}


def _empty_wordbook() -> dict[str, Any]:
    return {"words": {}}


def _normalize_wordbook_id(wordbook_id: str | None) -> str:
    return normalize_wordbook_id(wordbook_id or DEFAULT_WORDBOOK_ID)


class LearnedWordsFileStore:
    """读写 learned_words.json。"""

    def __init__(self, path: Path | str = LEARNED_WORDS_FILE) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._save(_empty_root())

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return _empty_root()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_root()
        if not isinstance(data, dict):
            return _empty_root()
        if "wordbooks" not in data or not isinstance(data["wordbooks"], dict):
            data["wordbooks"] = {}
        data.setdefault("version", FILE_VERSION)
        return data

    def _save(self, data: dict[str, Any]) -> None:
        data["version"] = FILE_VERSION
        save_json_atomic(self.path, data)

    def clear_all(self) -> None:
        """清空全部已学单词记录。"""
        self._save(_empty_root())

    def _words_map(self, data: dict[str, Any], wordbook_id: str) -> dict[str, dict[str, Any]]:
        wid = _normalize_wordbook_id(wordbook_id)
        wb = data["wordbooks"].setdefault(wid, _empty_wordbook())
        words = wb.setdefault("words", {})
        if not isinstance(words, dict):
            words = {}
            wb["words"] = words
        return words

    def mark_learned_words(self, words: Iterable[str], wordbook_id: str | None = None) -> int:
        now = _utc_now_iso()
        clean = [str(w).strip() for w in words if str(w).strip()]
        if not clean:
            return 0

        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        for word in clean:
            if word in bucket:
                row = bucket[word]
                row["last_seen_at"] = now
                row["total_seen"] = int(row.get("total_seen", 0)) + 1
            else:
                bucket[word] = _new_word_row(word, now=now)
                bucket[word]["total_seen"] = 1
        self._save(data)
        return len(clean)

    def list_words(self, wordbook_id: str | None = None) -> list[str]:
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        return list(bucket.keys())

    def record_self_rating(
        self,
        word: str,
        choice: str,
        wordbook_id: str | None = None,
    ) -> dict[str, Any]:
        """记录阶段 1 自评（k=认识，u=不认识），维护最近 3 次滑动窗口。"""
        clean = str(word).strip()
        if not clean:
            raise ValueError("word is required")
        if choice not in VALID_SELF_RATING_CHOICES:
            raise ValueError("choice must be k or u")

        now = _utc_now_iso()
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        if clean not in bucket:
            bucket[clean] = _new_word_row(clean, now=now)
        row = bucket[clean]
        window = row.get("self_rating_window")
        if not isinstance(window, dict):
            window = _empty_self_rating_window()
        _push_self_rating_window(window, choice)
        row["self_rating_window"] = window
        row["last_seen_at"] = now
        self._save(data)
        return dict(window)

    def get_self_rating_window(
        self, word: str, wordbook_id: str | None = None
    ) -> dict[str, Any] | None:
        clean = str(word).strip()
        if not clean:
            return None
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        row = bucket.get(clean)
        if not row:
            return None
        window = row.get("self_rating_window")
        if not isinstance(window, dict):
            return _empty_self_rating_window()
        return dict(window)

    def get_learning_stats(
        self, wordbook_id: str | None = None, limit: int = 200
    ) -> dict[str, object]:
        safe_limit = max(1, min(int(limit), 1000))
        wid = _normalize_wordbook_id(wordbook_id or DEFAULT_WORDBOOK_ID)
        data = self._load()
        bucket = self._words_map(data, wid)
        rows = list(bucket.values())
        rows.sort(key=lambda r: str(r.get("last_seen_at", "")), reverse=True)

        words = [
            {
                "word": str(row.get("word", "")),
                "first_learned_at": str(row.get("first_learned_at", "")),
                "last_seen_at": str(row.get("last_seen_at", "")),
                "total_seen": int(row.get("total_seen", 0)),
                "self_rating_window": row.get("self_rating_window"),
            }
            for row in rows[:safe_limit]
        ]
        return {
            "wordbook_id": wid,
            "storage_file": str(self.path),
            "total_learned": len(rows),
            "words": words,
        }
