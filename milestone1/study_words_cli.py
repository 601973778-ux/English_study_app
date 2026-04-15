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
import json
import random
import re
from pathlib import Path
from typing import Iterable


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


def load_words(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到词库文件: {path}")

    words: list[dict[str, str]] = []
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

            word = str(item.get("word", "")).strip()
            content = str(item.get("content", "")).strip()
            if word:
                words.append({"word": word, "content": content})

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


def run_session(words: list[dict[str, str]], count: int, seed: int | None) -> None:
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
        word = item["word"]
        content = item["content"]
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
