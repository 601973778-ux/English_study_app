from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from Vocabulary_model.learned_words_store import (
    LEARNED_WORDS_FILE,
    VALID_PROFICIENCY,
    LearnedWordsFileStore,
)
from Vocabulary_model.wordbook_catalog import DEFAULT_WORDBOOK_ID


DB_FILE = Path(__file__).resolve().parent / "review_reciting.db"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_study_ratio(review_ratio: str) -> tuple[int, int]:
    """
    设置项「新学习 : 复习」比例，如 ``1:2`` 表示每 1 个新词配 2 个复习词。
    返回 (new_part, review_part)。
    """
    try:
        left_raw, right_raw = str(review_ratio).split(":", 1)
        new_part = int(left_raw)
        review_part = int(right_raw)
    except (ValueError, AttributeError):
        return 1, 1

    if new_part <= 0 or review_part <= 0:
        return 1, 1
    return new_part, review_part


def compute_review_target(daily_new_words: int, review_ratio: str) -> int:
    """每日复习词目标数 = 每日新词数 × (复习份数 / 新词份数)。"""
    if daily_new_words <= 0:
        return 0

    new_part, review_part = parse_study_ratio(review_ratio)
    return max(0, round(daily_new_words * review_part / new_part))


def compute_daily_quotas(daily_new_words: int, review_ratio: str) -> tuple[int, int]:
    """返回 (new_target, review_target)。"""
    new_target = max(0, int(daily_new_words))
    review_target = compute_review_target(new_target, review_ratio)
    return new_target, review_target


@dataclass(frozen=True, slots=True)
class ReviewPlan:
    review_words: list[str]
    review_target: int
    review_shortfall: int
    daily_words: int
    review_ratio: str


def _migrate_sqlite_to_file(file_store: LearnedWordsFileStore, db_path: Path) -> None:
    """一次性：将旧 SQLite 中的已学词导入 JSON（归入默认词书）。"""
    if not db_path.is_file():
        return
    if file_store.list_words(DEFAULT_WORDBOOK_ID):
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT word FROM learned_words").fetchall()
        conn.close()
    except (OSError, sqlite3.Error):
        return
    words = [str(r["word"]).strip() for r in rows if str(r["word"]).strip()]
    if words:
        file_store.mark_learned_words(words, wordbook_id=DEFAULT_WORDBOOK_ID)


class ReviewRecitingDataStore:
    """
    已学单词存储（JSON 文件，按词书分桶）。

    集成方式：
    1) 学习过程中调用 mark_learned_words(..., wordbook_id=...)
    2) 每日开课前调用 build_review_plan(..., wordbook_id=...)
    3) 将 review_words 并入当日学习池
    """

    def __init__(
        self,
        file_path: Path | str = LEARNED_WORDS_FILE,
        db_path: Path | str = DB_FILE,
    ) -> None:
        self._file = LearnedWordsFileStore(file_path)
        _migrate_sqlite_to_file(self._file, Path(db_path))

    def mark_learned_words(
        self, words: Iterable[str], wordbook_id: str | None = None
    ) -> int:
        return self._file.mark_learned_words(words, wordbook_id=wordbook_id)

    def build_review_plan(
        self,
        daily_new_words: int,
        review_ratio: str,
        seed: int | None = None,
        wordbook_id: str | None = None,
    ) -> ReviewPlan:
        review_target = compute_review_target(
            daily_new_words=daily_new_words, review_ratio=review_ratio
        )
        if review_target <= 0:
            return ReviewPlan(
                review_words=[],
                review_target=0,
                review_shortfall=0,
                daily_words=max(daily_new_words, 0),
                review_ratio=str(review_ratio),
            )

        candidates = self._file.list_words(wordbook_id=wordbook_id)
        rng = random.Random(seed)
        if len(candidates) <= review_target:
            selected = list(candidates)
            rng.shuffle(selected)
            shortfall = review_target - len(selected)
            return ReviewPlan(
                review_words=selected,
                review_target=review_target,
                review_shortfall=shortfall,
                daily_words=max(daily_new_words, 0),
                review_ratio=str(review_ratio),
            )

        selected = rng.sample(candidates, review_target)
        return ReviewPlan(
            review_words=selected,
            review_target=review_target,
            review_shortfall=0,
            daily_words=max(daily_new_words, 0),
            review_ratio=str(review_ratio),
        )

    def set_proficiency(
        self, word: str, proficiency: str, wordbook_id: str | None = None
    ) -> bool:
        return self._file.set_proficiency(word, proficiency, wordbook_id=wordbook_id)

    def mark_proficient(self, word: str, wordbook_id: str | None = None) -> bool:
        return self.set_proficiency(word, "proficient", wordbook_id=wordbook_id)

    def mark_fuzzy(self, word: str, wordbook_id: str | None = None) -> bool:
        return self.set_proficiency(word, "fuzzy", wordbook_id=wordbook_id)

    def mark_unfamiliar(self, word: str, wordbook_id: str | None = None) -> bool:
        return self.set_proficiency(word, "unfamiliar", wordbook_id=wordbook_id)

    def update_answer_result(
        self, word: str, result: str, wordbook_id: str | None = None
    ) -> bool:
        return self._file.update_answer_result(word, result, wordbook_id=wordbook_id)

    def get_words_by_proficiency(
        self, proficiency: str, wordbook_id: str | None = None
    ) -> list[str]:
        return self._file.get_words_by_proficiency(proficiency, wordbook_id=wordbook_id)

    def get_learning_stats(
        self, limit: int = 200, wordbook_id: str | None = None
    ) -> dict[str, object]:
        return self._file.get_learning_stats(wordbook_id=wordbook_id, limit=limit)


__all__ = [
    "DB_FILE",
    "LEARNED_WORDS_FILE",
    "VALID_PROFICIENCY",
    "ReviewPlan",
    "ReviewRecitingDataStore",
    "compute_review_target",
    "compute_daily_quotas",
    "parse_study_ratio",
]
