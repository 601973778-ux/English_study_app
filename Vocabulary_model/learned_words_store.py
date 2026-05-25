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

VALID_PROFICIENCY = frozenset({"unclassified", "proficient", "fuzzy", "unfamiliar"})


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
                bucket[word] = {
                    "word": word,
                    "first_learned_at": now,
                    "last_seen_at": now,
                    "total_seen": 1,
                    "proficiency": "unclassified",
                    "correct_count": 0,
                    "fuzzy_count": 0,
                    "incorrect_count": 0,
                }
        self._save(data)
        return len(clean)

    def list_words(self, wordbook_id: str | None = None) -> list[str]:
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        return list(bucket.keys())

    def set_proficiency(self, word: str, proficiency: str, wordbook_id: str | None = None) -> bool:
        if proficiency not in VALID_PROFICIENCY:
            raise ValueError(f"invalid proficiency: {proficiency}")
        clean = str(word).strip()
        if not clean:
            return False
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        if clean not in bucket:
            return False
        bucket[clean]["proficiency"] = proficiency
        bucket[clean]["last_seen_at"] = _utc_now_iso()
        self._save(data)
        return True

    def update_answer_result(
        self, word: str, result: str, wordbook_id: str | None = None
    ) -> bool:
        clean = str(word).strip()
        if not clean:
            return False
        column_map = {
            "correct": "correct_count",
            "fuzzy": "fuzzy_count",
            "incorrect": "incorrect_count",
        }
        column = column_map.get(str(result))
        if not column:
            raise ValueError("result must be one of: correct, fuzzy, incorrect")

        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        if clean not in bucket:
            return False
        bucket[clean][column] = int(bucket[clean].get(column, 0)) + 1
        bucket[clean]["last_seen_at"] = _utc_now_iso()
        self._save(data)
        return True

    def get_words_by_proficiency(
        self, proficiency: str, wordbook_id: str | None = None
    ) -> list[str]:
        if proficiency not in VALID_PROFICIENCY:
            raise ValueError(f"invalid proficiency: {proficiency}")
        data = self._load()
        bucket = self._words_map(data, wordbook_id or DEFAULT_WORDBOOK_ID)
        return [w for w, row in bucket.items() if row.get("proficiency") == proficiency]

    def get_learning_stats(
        self, wordbook_id: str | None = None, limit: int = 200
    ) -> dict[str, object]:
        safe_limit = max(1, min(int(limit), 1000))
        wid = _normalize_wordbook_id(wordbook_id or DEFAULT_WORDBOOK_ID)
        data = self._load()
        bucket = self._words_map(data, wid)
        rows = list(bucket.values())
        rows.sort(key=lambda r: str(r.get("last_seen_at", "")), reverse=True)

        proficient = fuzzy = unfamiliar = unclassified = 0
        for row in rows:
            p = str(row.get("proficiency", "unclassified"))
            if p == "proficient":
                proficient += 1
            elif p == "fuzzy":
                fuzzy += 1
            elif p == "unfamiliar":
                unfamiliar += 1
            else:
                unclassified += 1

        words = [
            {
                "word": str(row.get("word", "")),
                "proficiency": str(row.get("proficiency", "unclassified")),
                "first_learned_at": str(row.get("first_learned_at", "")),
                "last_seen_at": str(row.get("last_seen_at", "")),
                "total_seen": int(row.get("total_seen", 0)),
            }
            for row in rows[:safe_limit]
        ]
        return {
            "wordbook_id": wid,
            "storage_file": str(self.path),
            "total_learned": len(rows),
            "proficient_count": proficient,
            "fuzzy_count": fuzzy,
            "unfamiliar_count": unfamiliar,
            "unclassified_count": unclassified,
            "words": words,
        }
