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


def load_words(path: Path) -> list[Entry]:
    if not path.exists():
        raise FileNotFoundError(f"找不到词库文件: {path}")

    words: list[Entry] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                # 遇到坏行时跳过，避免单条数据影响整体学习
                continue

            # 兼容不同字段名：word / words
            word = str(item.get("word", "")).strip() or str(item.get("words", "")).strip()
            content = str(item.get("content", "")).strip()
            if word:
                words.append(Entry(word=word, content=content))

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
        self.daily_pool: list[Entry] = random.sample(entries, actual_count)
        self.active_pool: list[Entry] = list(self.daily_pool)
        self.current: Entry | None = None
        self.review_count = 0
        self.review_mode: ReviewMode = ""
        self.waiting_next_after_meaning = False

        self.remembered_words: set[str] = set()
        self.fuzzy_words: set[str] = set()
        self.unknown_words: set[str] = set()

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
                "word": "本次学习完成",
                "meaning": "你可以点击“开始学习”开启下一轮 50 词。",
                "meta": self._meta_text(),
                "ui": {
                    "startEnabled": True,
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

        if self.waiting_next_after_meaning:
            return {
                "phase": "meaning",
                "word": self.current.word,
                "meaning": f"词义：{extract_meaning_only(self.current.content)}",
                "meta": self._meta_text(),
                "ui": {
                    "startEnabled": False,
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
            "ui": {
                "startEnabled": False,
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
        self.fuzzy_words.add(self.current.word)
        self.remembered_words.discard(self.current.word)
        self.unknown_words.discard(self.current.word)
        self._show_current_word()
        return self.state()

    def next_after_meaning(self) -> dict:
        if not self.waiting_next_after_meaning:
            return self.state()
        if self.review_mode == "known" and self.current:
            self.remembered_words.add(self.current.word)
            self.fuzzy_words.discard(self.current.word)
            self.unknown_words.discard(self.current.word)
            self.active_pool = [e for e in self.active_pool if e.word != self.current.word]
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
