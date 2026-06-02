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
from typing import Any, Iterable, Literal


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
REINFORCE_STAGE_COUNT = 3


class StudySession:
    """
    学习会话（认识/不认识），供 CLI 与 Web 复用。
    - 阶段 1：自评（认识/不认识 → 释义 → 下一个/记错了）
    - 阶段 2：四选一（形近/语义近干扰项）
    - 阶段 3：例句填空
    - 不认识/记错：回到阶段 1；词留在当日复习/新学池随机再出现
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
        self.review_word_set: set[str] = set()
        self.new_word_set: set[str] = set()
        self.reinforce_stage: dict[str, int] = {}
        self.mcq_variant: dict[str, int] = {}
        self.word_reinforce: set[str] = set()

    @classmethod
    def from_daily_state(
        cls,
        entries: list[Entry],
        *,
        planned_words: list[str],
        completed_words: set[str],
        review_words: list[str] | None = None,
        new_words: list[str] | None = None,
        snapshot: dict | None = None,
    ) -> StudySession:
        by_word = {e.word: e for e in entries}
        daily_pool = [by_word[w] for w in planned_words if w in by_word]
        active_set = {w for w in planned_words if w not in completed_words}
        active_pool = [by_word[w] for w in planned_words if w in active_set and w in by_word]

        session = cls.__new__(cls)
        session._init_pools(daily_pool, active_pool, completed_words)
        session.review_word_set = {str(w).strip() for w in (review_words or []) if str(w).strip()}
        session.new_word_set = {str(w).strip() for w in (new_words or []) if str(w).strip()}
        if not session.new_word_set:
            session.new_word_set = {
                w for w in active_set if w not in session.review_word_set
            }

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
            raw_stages = snapshot.get("reinforce_stage") or {}
            if isinstance(raw_stages, dict) and raw_stages:
                session.reinforce_stage = {
                    str(k): max(1, min(3, int(v)))
                    for k, v in raw_stages.items()
                    if str(k).strip()
                }
            else:
                raw_streaks = snapshot.get("word_streaks") or {}
                if isinstance(raw_streaks, dict):
                    for k, v in raw_streaks.items():
                        w = str(k).strip()
                        if not w:
                            continue
                        streak = int(v)
                        if streak <= 0:
                            session.reinforce_stage[w] = 1
                        elif streak == 1:
                            session.reinforce_stage[w] = 2
                        else:
                            session.reinforce_stage[w] = 3
            raw_variants = snapshot.get("mcq_variant") or {}
            if isinstance(raw_variants, dict):
                session.mcq_variant = {
                    str(k): max(0, int(v))
                    for k, v in raw_variants.items()
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
                restored = [by_w[w] for w in saved_active if w in by_w]
                extra = [e for e in session.active_pool if e.word not in {x.word for x in restored}]
                session.active_pool = restored + extra
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
            "reinforce_stage": dict(self.reinforce_stage),
            "mcq_variant": dict(self.mcq_variant),
            "word_reinforce": sorted(self.word_reinforce),
        }

    def _reinforce_stage_of(self, word: str) -> int:
        clean = str(word).strip()
        if not clean or clean not in self.word_reinforce:
            return 0
        return max(1, min(3, int(self.reinforce_stage.get(clean, 1))))

    def _word_progress_payload(self, word: str) -> dict[str, int | bool | str]:
        reinforce = word in self.word_reinforce
        stage = self._reinforce_stage_of(word) if reinforce else 0
        labels = {1: "自评", 2: "释义四选一", 3: "选词四选一"}
        return {
            "reinforce": reinforce,
            "stage": stage,
            "required": REINFORCE_STAGE_COUNT,
            "stage_label": labels.get(stage, ""),
            "mcq_variant": int(self.mcq_variant.get(word, 0)) if reinforce else 0,
            "streak": max(0, stage - 1) if reinforce else 0,
        }

    def _mark_reinforce(self, word: str, *, reset_variant: bool = True) -> None:
        clean = str(word).strip()
        if not clean:
            return
        self.word_reinforce.add(clean)
        self.reinforce_stage[clean] = 1
        if reset_variant:
            self.mcq_variant[clean] = 0

    def _graduate_word(self, word: str) -> None:
        clean = str(word).strip()
        if not clean:
            return
        self.remembered_words.add(clean)
        self.fuzzy_words.discard(clean)
        self.unknown_words.discard(clean)
        self.completed_words.add(clean)
        self.active_pool = [e for e in self.active_pool if e.word != clean]
        self.reinforce_stage.pop(clean, None)
        self.mcq_variant.pop(clean, None)
        self.word_reinforce.discard(clean)

    def peek_word_completed_on_next(self) -> str | None:
        """若下一次 next 会算作「今日完成」，返回该词（调用 next 前使用）。"""
        if (
            self.waiting_next_after_meaning
            and self.review_mode == "known"
            and self.current
        ):
            word = self.current.word
            # 未进入巩固的词：认识→下一个 一次通过即毕业
            if word not in self.word_reinforce:
                return word
        return None

    def apply_quiz_result(
        self, word: str, result: dict[str, Any]
    ) -> str | None:
        """应用测验结果；若毕业返回该词。"""
        clean = str(word).strip()
        if not clean or clean not in self.word_reinforce:
            return None
        if result.get("graduated"):
            self._graduate_word(clean)
            self._show_current_word()
            return clean
        stage = int(result.get("stage") or 0)
        if result.get("correct") and stage in (2, 3):
            next_stage = result.get("next_stage")
            if isinstance(next_stage, int) and 1 <= next_stage <= 3:
                self.reinforce_stage[clean] = next_stage
            if result.get("pick_next_word"):
                self._show_current_word()
        elif result.get("advance_variant"):
            self.mcq_variant[clean] = int(self.mcq_variant.get(clean, 0)) + 1
        else:
            next_stage = result.get("next_stage")
            if isinstance(next_stage, int) and 1 <= next_stage <= 3:
                self.reinforce_stage[clean] = next_stage
        self.waiting_next_after_meaning = False
        self.review_mode = ""
        return None

    def back_to_reinforce_stage1(self) -> None:
        if not self.current:
            return
        word = self.current.word
        self._mark_reinforce(word, reset_variant=True)
        self.fuzzy_words.add(word)
        self.remembered_words.discard(word)
        self.unknown_words.discard(word)
        self.waiting_next_after_meaning = False
        self.review_mode = ""
        self._show_current_word()

    def _meta_text(self) -> str:
        return (
            f"今日词库 {len(self.daily_pool)} | 待巩固 {len(self.active_pool)} | "
            f"已记住 {len(self.remembered_words)} | 记忆模糊 {len(self.fuzzy_words)} | "
            f"不认识 {len(self.unknown_words)} | 已抽查 {self.review_count}"
        )

    def _segment_active_entries(self) -> list[Entry]:
        """复习段未完成时只从复习池随机抽；否则从新学池随机抽。"""
        review_active = [e for e in self.active_pool if e.word in self.review_word_set]
        if review_active:
            return review_active
        if self.new_word_set:
            new_active = [e for e in self.active_pool if e.word in self.new_word_set]
            if new_active:
                return new_active
        fallback = [e for e in self.active_pool if e.word not in self.review_word_set]
        return fallback if fallback else list(self.active_pool)

    def _pick_next_word(self) -> Entry | None:
        pool = self._segment_active_entries()
        if not pool:
            return None
        if len(pool) == 1:
            return pool[0]
        cur = self.current.word if self.current else ""
        candidates = [e for e in pool if e.word != cur]
        bucket = candidates if candidates else pool
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
        reinforce_stage = self._reinforce_stage_of(self.current.word)

        if reinforce_stage >= 2 and not self.waiting_next_after_meaning:
            labels = {2: "释义四选一", 3: "选词四选一"}
            return {
                "phase": "reinforce_quiz",
                "quizStage": reinforce_stage,
                "word": self.current.word,
                "meaning": labels.get(reinforce_stage, "巩固测验"),
                "meta": self._meta_text(),
                "phonetic": phonetic,
                "examplePhrase": "",
                "wordProgress": word_progress,
                "ui": {
                    "startEnabled": False,
                    "startLabel": "开始学习",
                    "knownEnabled": False,
                    "unknownEnabled": False,
                    "showMistake": True,
                    "showNext": False,
                    "showQuiz": True,
                },
            }

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

    def current_entry(self) -> Entry | None:
        return self.current

    def quiz_context(self) -> dict[str, Any] | None:
        if not self.current:
            return None
        word = self.current.word
        stage = self._reinforce_stage_of(word)
        if stage < 2:
            return None
        return {
            "word": word,
            "stage": stage,
            "variant": int(self.mcq_variant.get(word, 0)),
        }

    def mistake_after_known(self) -> dict:
        if not self.current:
            return self.state()
        if self._reinforce_stage_of(self.current.word) >= 2:
            self.back_to_reinforce_stage1()
            return self.state()
        if not self.waiting_next_after_meaning or self.review_mode != "known":
            return self.state()
        word = self.current.word
        self._mark_reinforce(word)
        self.fuzzy_words.add(word)
        self.remembered_words.discard(word)
        self.unknown_words.discard(word)
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
                    if self._reinforce_stage_of(word) == 1:
                        self.reinforce_stage[word] = 2
                        self.waiting_next_after_meaning = False
                        self.review_mode = ""
                        self._show_current_word()
                        return self.state()
                else:
                    self._graduate_word(word)
            elif self.review_mode == "unknown":
                self._mark_reinforce(word)
        self._show_current_word()
        return self.state()


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
