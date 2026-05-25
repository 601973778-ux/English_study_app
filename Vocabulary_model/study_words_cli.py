#!/usr/bin/env python3
"""
命令行背单词脚本。

功能：
1. 每次学习从词库随机抽取 50 个单词（可通过参数调整）。
2. 一次只显示一个英文单词。
3. 用户输入：
   - y: 认识，进入下一个单词
   - n: 不认识，显示中文释义后进入下一个单词
   - q: 退出本次学习
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
import re
from pathlib import Path
from typing import Iterable, Literal


DEFAULT_SOURCE = Path(__file__).resolve().parent.parent / "DictionaryByGPT4-main" / "gptwords.json"
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI 背单词：认识/不认识学习模式")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="词库文件路径（默认使用 DictionaryByGPT4 的 gptwords.json）",
    )
    parser.add_argument("--count", type=int, default=50, help="每次学习抽取单词数量，默认 50")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（可选，便于复现）")
    return parser.parse_args()


@dataclasses.dataclass(frozen=True, slots=True)
class Entry:
    word: str
    content: str
    phonetic: str = ""
    example_phrase: str = ""
    display_meaning: str | None = None
    gloss1: str = ""


def _is_structured_wordbook_item(item: dict) -> bool:
    return "词性1" in item or ("音标" in item and "释义1" in item)


def _structured_item_to_entry(item: dict, word: str) -> Entry:
    phonetic = str(item.get("音标", "")).strip()
    example = str(item.get("示例&短句", item.get("示例与短句", ""))).strip()
    lines: list[str] = []
    for i in range(1, 48):
        pos = item.get(f"词性{i}")
        gloss = item.get(f"释义{i}")
        if pos is None and gloss is None:
            if i == 1:
                continue
            break
        ps = str(pos or "").strip()
        gs = str(gloss or "").strip()
        if ps or gs:
            if ps and gs:
                lines.append(f"{ps} {gs}")
            elif gs:
                lines.append(gs)
            elif ps:
                lines.append(ps)
    display = "\n".join(lines).strip()
    if not display:
        display = str(item.get("content", "")).strip() or "（暂无释义）"
    gloss1 = str(item.get("释义1", "")).strip()
    content_parts = [display]
    if example:
        content_parts.append(example)
    content = "\n".join(content_parts)
    return Entry(
        word=word,
        content=content,
        phonetic=phonetic,
        example_phrase=example,
        display_meaning=display,
        gloss1=gloss1,
    )


def _item_to_entry(item: dict) -> Entry | None:
    word = str(item.get("word", "")).strip() or str(item.get("words", "")).strip()
    if not word:
        return None
    if _is_structured_wordbook_item(item):
        return _structured_item_to_entry(item, word)
    content = str(item.get("content", "")).strip()
    return Entry(word=word, content=content)


def load_words(path: Path) -> list[Entry]:
    if not path.exists():
        raise FileNotFoundError(f"找不到词库文件: {path}")

    raw_text = path.read_text(encoding="utf-8").strip()
    words: list[Entry] = []

    if path.suffix.lower() == ".json" and raw_text.startswith("["):
        try:
            arr = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {path}") from e
        if not isinstance(arr, list):
            raise ValueError(f"JSON 根类型应为数组: {path}")
        for item in arr:
            if not isinstance(item, dict):
                continue
            ent = _item_to_entry(item)
            if ent is not None:
                words.append(ent)
    else:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                ent = _item_to_entry(item)
                if ent is not None:
                    words.append(ent)

    if not words:
        raise ValueError(f"词库为空或格式不正确: {path}")
    return words


def _clean_line_candidates(lines: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        line = re.sub(r"^[-*>\d\.\)\s]+", "", line).strip()
        if line:
            cleaned.append(line)
    return cleaned


def extract_chinese_meaning(content: str) -> str:
    if not content:
        return "（暂无释义）"

    lines = _clean_line_candidates(content.splitlines())
    for line in lines:
        if CHINESE_RE.search(line):
            # 优先返回第一句中文，避免太长
            parts = re.split(r"[。！？!?\n]", line)
            for part in parts:
                text = part.strip()
                if CHINESE_RE.search(text):
                    return text
            return line

    # 如果没检测到中文，就给一个简短英文兜底
    text = re.sub(r"\s+", " ", content).strip()
    return text[:120] + ("..." if len(text) > 120 else "")


_MEANING_START_RE = re.compile(
    r"^(?:\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:分析词义|词义分析)\s*[:：]?\s*(?:\*\*)?\s*)(.*)$",
    re.MULTILINE,
)
_MEANING_END_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"(?:列举例句|例句|词根分析|词缀分析|发展历史和文化背景|发展历史|单词变形|记忆辅助|小故事)\s*[:：]?\s*(?:\*\*)?\s*(?:$|\n)",
    re.MULTILINE,
)
_MEANING_HEADER_TRIM_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:分析词义|词义分析)\s*[:：]?\s*(?:\*\*)?\s*",
    re.IGNORECASE,
)


def extract_meaning_only(content: str) -> str:
    """
    从 GPT 的 content 中提取“词义分析”部分（更适合前端显示）。
    如果结构不规范，回退为中文优先的短释义。
    """
    text = str(content or "").replace("\r\n", "\n").strip()
    if not text:
        return "（暂无释义）"

    start = _MEANING_START_RE.search(text)
    body = text
    if start:
        inline = (start.group(1) or "").strip()
        if inline:
            body = text[start.start() + start.group(0).find(start.group(1)) :]
        else:
            body = text[start.end() :]

    end = _MEANING_END_RE.search(body)
    if end:
        body = body[: end.start()]

    body = _MEANING_HEADER_TRIM_RE.sub("", body, count=1)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body or extract_chinese_meaning(text)


ReviewMode = Literal["", "known", "unknown"]
REINFORCE_STREAK_REQUIRED = 3


class StudySession:
    """
    学习会话（认识/不认识），供 CLI 与 Web 复用。
    - question 阶段：只显示单词，等待 known/unknown
    - meaning 阶段：显示词义，等待 next；若是 known，可额外 mistake
    """

    def __init__(self, entries: list[Entry], count: int, seed: int | None = None) -> None:
        if count <= 0:
            raise ValueError("count 必须大于 0")
        if seed is not None:
            random.seed(seed)

        actual_count = min(count, len(entries))
        planned = random.sample(entries, actual_count)
        self._init_pools(planned, planned, set())

    def _init_pools(
        self,
        daily_pool: list[Entry],
        active_pool: list[Entry],
        completed_words: set[str],
    ) -> None:
        self.daily_pool: list[Entry] = list(daily_pool)
        self.active_pool: list[Entry] = list(active_pool)
        self.completed_words: set[str] = set(completed_words)
        self.current: Entry | None = None
        self.review_count = 0
        self.review_mode: ReviewMode = ""
        self.waiting_next_after_meaning = False
        self.remembered_words: set[str] = set()
        self.fuzzy_words: set[str] = set()
        self.unknown_words: set[str] = set()
        self.sequential_order = False
        self.review_word_set: set[str] = set()
        self.word_streaks: dict[str, int] = {}
        self.word_reinforce: set[str] = set()

    @classmethod
    def from_daily_state(
        cls,
        entries: list[Entry],
        *,
        planned_words: list[str],
        completed_words: set[str],
        review_words: list[str] | None = None,
        snapshot: dict | None = None,
    ) -> StudySession:
        by_word = {e.word: e for e in entries}
        daily_pool = [by_word[w] for w in planned_words if w in by_word]
        active_set = {w for w in planned_words if w not in completed_words}
        active_pool = [by_word[w] for w in planned_words if w in active_set and w in by_word]

        session = cls.__new__(cls)
        session._init_pools(daily_pool, active_pool, completed_words)
        session.sequential_order = True
        session.review_word_set = {str(w).strip() for w in (review_words or []) if str(w).strip()}

        if snapshot:
            session.review_count = int(snapshot.get("review_count", 0))
            session.review_mode = snapshot.get("review_mode") or ""
            if session.review_mode not in ("", "known", "unknown"):
                session.review_mode = ""
            session.waiting_next_after_meaning = bool(
                snapshot.get("waiting_next_after_meaning", False)
            )
            session.remembered_words = set(snapshot.get("remembered_words") or [])
            session.fuzzy_words = set(snapshot.get("fuzzy_words") or [])
            session.unknown_words = set(snapshot.get("unknown_words") or [])
            raw_streaks = snapshot.get("word_streaks") or {}
            if isinstance(raw_streaks, dict):
                session.word_streaks = {
                    str(k): int(v)
                    for k, v in raw_streaks.items()
                    if str(k).strip()
                }
            session.word_reinforce = {
                str(w).strip()
                for w in (snapshot.get("word_reinforce") or [])
                if str(w).strip()
            }
            saved_active = snapshot.get("active_words") or []
            if isinstance(saved_active, list) and saved_active:
                by_w = {e.word: e for e in session.active_pool}
                ordered = [by_w[w] for w in saved_active if w in by_w]
                tail = [e for e in session.active_pool if e.word not in {x.word for x in ordered}]
                session.active_pool = ordered + tail
            cur = str(snapshot.get("current_word") or "").strip()
            session.current = by_word.get(cur) if cur else None
            if session.current and session.current.word not in active_set:
                session.current = None
        return session

    def to_snapshot(self) -> dict:
        return {
            "current_word": self.current.word if self.current else "",
            "review_count": self.review_count,
            "review_mode": self.review_mode,
            "waiting_next_after_meaning": self.waiting_next_after_meaning,
            "remembered_words": sorted(self.remembered_words),
            "fuzzy_words": sorted(self.fuzzy_words),
            "unknown_words": sorted(self.unknown_words),
            "active_words": [e.word for e in self.active_pool],
            "word_streaks": dict(self.word_streaks),
            "word_reinforce": sorted(self.word_reinforce),
        }

    def _word_progress_payload(self, word: str) -> dict[str, int | bool]:
        reinforce = word in self.word_reinforce
        required = REINFORCE_STREAK_REQUIRED if reinforce else 1
        streak = int(self.word_streaks.get(word, 0))
        return {
            "reinforce": reinforce,
            "streak": streak,
            "required": required,
        }

    def _mark_reinforce(self, word: str) -> None:
        clean = str(word).strip()
        if not clean:
            return
        self.word_reinforce.add(clean)
        self.word_streaks[clean] = 0

    def _requeue_to_end(self, word: str) -> None:
        clean = str(word).strip()
        if not clean:
            return
        entry = next((e for e in self.active_pool if e.word == clean), None)
        if entry is None:
            return
        rest = [e for e in self.active_pool if e.word != clean]
        self.active_pool = rest + [entry]

    def _graduate_word(self, word: str) -> None:
        clean = str(word).strip()
        if not clean:
            return
        self.remembered_words.add(clean)
        self.fuzzy_words.discard(clean)
        self.unknown_words.discard(clean)
        self.completed_words.add(clean)
        self.active_pool = [e for e in self.active_pool if e.word != clean]
        self.word_streaks.pop(clean, None)
        self.word_reinforce.discard(clean)

    def _will_graduate_on_known_next(self, word: str) -> bool:
        clean = str(word).strip()
        if not clean:
            return False
        if clean not in self.word_reinforce:
            return True
        return self.word_streaks.get(clean, 0) + 1 >= REINFORCE_STREAK_REQUIRED

    def _meta_text(self) -> str:
        return (
            f"今日词库 {len(self.daily_pool)} | 待巩固 {len(self.active_pool)} | "
            f"已记住 {len(self.remembered_words)} | 记忆模糊 {len(self.fuzzy_words)} | "
            f"不认识 {len(self.unknown_words)} | 已抽查 {self.review_count}"
        )

    def _pick_next_word(self) -> Entry | None:
        if not self.active_pool:
            return None
        if len(self.active_pool) == 1:
            return self.active_pool[0]
        if self.sequential_order:
            cur = self.current.word if self.current else ""
            passed_current = not cur
            for entry in self.active_pool:
                if passed_current:
                    return entry
                if entry.word == cur:
                    passed_current = True
            for entry in self.active_pool:
                if entry.word != cur:
                    return entry
            return self.active_pool[0]
        candidates = [e for e in self.active_pool if e.word != (self.current.word if self.current else "")]
        bucket = candidates if candidates else self.active_pool
        return random.choice(bucket)

    def _show_current_word(self) -> None:
        self.current = self._pick_next_word()
        if not self.current:
            return
        self.review_count += 1
        self.review_mode = ""
        self.waiting_next_after_meaning = False

    def start(self) -> dict:
        self._show_current_word()
        return self.state()

    def state(self) -> dict:
        if not self.active_pool:
            return {
                "phase": "finished",
                "word": "今日学习任务已完成",
                "meaning": "今日计划内的单词已全部学完，明天将开启新计划。",
                "meta": self._meta_text(),
                "phonetic": "",
                "examplePhrase": "",
                "ui": {
                    "startEnabled": True,
                    "startLabel": "返回",
                    "knownEnabled": False,
                    "unknownEnabled": False,
                    "showMistake": False,
                    "showNext": False,
                },
            }

        if not self.current:
            self._show_current_word()
            if not self.current:
                return self.state()

        phonetic = (self.current.phonetic or "").strip() if self.current else ""
        example_phrase = (self.current.example_phrase or "").strip() if self.current else ""

        word_progress = self._word_progress_payload(self.current.word)

        if self.waiting_next_after_meaning:
            if self.current.display_meaning is not None:
                meaning_text = self.current.display_meaning.strip() or "（暂无释义）"
            else:
                meaning_text = f"词义：{extract_meaning_only(self.current.content)}"
            return {
                "phase": "meaning",
                "word": self.current.word,
                "meaning": meaning_text,
                "meta": self._meta_text(),
                "phonetic": phonetic,
                "examplePhrase": example_phrase,
                "wordProgress": word_progress,
                "ui": {
                    "startEnabled": False,
                    "startLabel": "开始学习",
                    "knownEnabled": False,
                    "unknownEnabled": False,
                    "showMistake": self.review_mode == "known",
                    "showNext": True,
                },
            }

        return {
            "phase": "question",
            "word": self.current.word,
            "meaning": "请先判断是否认识，点击后会显示词义。",
            "meta": self._meta_text(),
            "phonetic": phonetic,
            "examplePhrase": "",
            "wordProgress": word_progress,
            "ui": {
                "startEnabled": False,
                "startLabel": "开始学习",
                "knownEnabled": True,
                "unknownEnabled": True,
                "showMistake": False,
                "showNext": False,
            },
        }

    def answer_known(self) -> dict:
        if not self.current or self.waiting_next_after_meaning:
            return self.state()
        self.waiting_next_after_meaning = True
        self.review_mode = "known"
        return self.state()

    def answer_unknown(self) -> dict:
        if not self.current or self.waiting_next_after_meaning:
            return self.state()
        self.unknown_words.add(self.current.word)
        self.remembered_words.discard(self.current.word)
        self.fuzzy_words.discard(self.current.word)
        self.waiting_next_after_meaning = True
        self.review_mode = "unknown"
        return self.state()

    def mistake_after_known(self) -> dict:
        if not self.current or not self.waiting_next_after_meaning or self.review_mode != "known":
            return self.state()
        word = self.current.word
        self._mark_reinforce(word)
        self.fuzzy_words.add(word)
        self.remembered_words.discard(word)
        self.unknown_words.discard(word)
        self._requeue_to_end(word)
        self.waiting_next_after_meaning = False
        self.review_mode = ""
        self._show_current_word()
        return self.state()

    def next_after_meaning(self) -> dict:
        if not self.waiting_next_after_meaning:
            return self.state()
        if self.current:
            word = self.current.word
            if self.review_mode == "known":
                if word in self.word_reinforce:
                    streak = self.word_streaks.get(word, 0) + 1
                    self.word_streaks[word] = streak
                    if streak >= REINFORCE_STREAK_REQUIRED:
                        self._graduate_word(word)
                    else:
                        self._requeue_to_end(word)
                else:
                    self._graduate_word(word)
            elif self.review_mode == "unknown":
                self._mark_reinforce(word)
                self._requeue_to_end(word)
        self._show_current_word()
        return self.state()

    def peek_word_completed_on_next(self) -> str | None:
        """若下一次 next 会算作「今日完成」，返回该词（调用 next 前使用）。"""
        if (
            self.waiting_next_after_meaning
            and self.review_mode == "known"
            and self.current
            and self._will_graduate_on_known_next(self.current.word)
        ):
            return self.current.word
        return None


def run_session(words: list[Entry], count: int, seed: int | None) -> None:
    if count <= 0:
        raise ValueError("count 必须大于 0")

    if seed is not None:
        random.seed(seed)

    actual_count = min(count, len(words))
    selected = random.sample(words, actual_count)

    known = 0
    unknown = 0

    print(f"\n已从词库抽取 {actual_count} 个单词，开始学习。\n")
    print("输入说明：y=认识，n=不认识（显示中文释义），q=退出\n")

    for idx, item in enumerate(selected, start=1):
        word = item.word
        content = item.content
        print(f"[{idx}/{actual_count}] {word}")

        while True:
            answer = input("你认识吗？(y/n/q): ").strip().lower()
            if answer == "y":
                known += 1
                print()
                break
            if answer == "n":
                unknown += 1
                print(f"中文释义：{extract_chinese_meaning(content)}\n")
                break
            if answer == "q":
                print("\n已提前结束学习。")
                print(f"当前统计：认识 {known} 个，不认识 {unknown} 个。")
                return
            print("请输入 y / n / q")

    print("学习结束。")
    print(f"统计：总数 {actual_count}，认识 {known}，不认识 {unknown}。")


def main() -> None:
    args = parse_args()
    words = load_words(args.source)
    run_session(words, args.count, args.seed)


if __name__ == "__main__":
    main()
