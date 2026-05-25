#!/usr/bin/env python3
"""
将 english-wordlists-master/CET6_edited.txt 转为 JSON。
字段：word、音标、词性1/释义1/…、示例&短句（首个 || 之后全文）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "english-wordlists-master" / "english-wordlists-master" / "CET6_edited.txt"
OUT = Path(__file__).resolve().parent / "CET6_edited.json"

# 词性标记：先匹配复合，再匹配简单（顺序重要）
_POS_CORE = (
    r"n\.\s*&\s*v\."
    r"|v\.\s*&\s*n\."
    r"|n\.|v\.|adj\.|adv\.|a\.|prep\.|conj\.|pron\.|vt\.|vi\.|art\.|int\.|num\.|aux\.|det\."
)
POS_BLOCK = re.compile(
    rf"(\[[^\]]+\]\s*)?({_POS_CORE})\s+",
    re.IGNORECASE,
)


def _wrap_ipa(s: str) -> str:
    t = s.strip()
    if not t:
        return ""
    if t.startswith("[") and t.endswith("]"):
        return t
    return f"[{t}]"


def normalize_head(line: str) -> str:
    """把少数非标准行改成「word [ipa] 余下」形态，便于统一解析。"""
    s = line.strip()
    if not s:
        return s

    # 已有标准 word [ipa] …
    if re.match(r"^.+?\s+\[[^\]]+\]\s", s):
        return s

    # plateau / ˈplætəʊ n. 高原
    m = re.match(r"^([A-Za-z'-]+)\s*/\s*(\S+?)\s+(n\.|v\.|adj\.|adv\.|a\.|prep\.|conj\.|pron\.)\s+(.*)$", s, re.I)
    if m:
        w, ipa, pos, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"{w} {_wrap_ipa(ipa)} {pos} {tail}"

    # rival /ˈraɪvəl n. …
    m = re.match(r"^([A-Za-z'-]+)\s*/\s*(\[?[^\]\s]+\]?)\s+(n\.|v\.|adj\.|adv\.|a\.|prep\.|conj\.|pron\.)\s+(.*)$", s, re.I)
    if m:
        w, ipa, pos, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"{w} {_wrap_ipa(ipa)} {pos} {tail}"

    # arbitrary ˈɑːbɪtrərɪ /adj. …
    m = re.match(
        r"^([A-Za-z'-]+)\s+([^\s/\[]+?)\s+/(n\.|v\.|adj\.|adv\.|a\.|prep\.|conj\.|pron\.)\s+(.*)$",
        s,
        re.I,
    )
    if m:
        w, ipa, pos, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"{w} {_wrap_ipa(ipa)} {pos} {tail}"

    return s


def split_examples(head: str) -> tuple[str, str]:
    if "||" not in head:
        return head, ""
    a, b = head.split("||", 1)
    return a.strip(), b.strip()


def parse_entry(line: str) -> dict[str, str] | None:
    raw = line.strip()
    if not raw:
        return None

    head, examples = split_examples(raw)
    head = normalize_head(head)

    m = re.match(r"^(?P<word>.+?)\s+(?P<first_ipa>\[[^\]]+\])\s*(?P<tail>.*)$", head)
    if not m:
        return {
            "word": raw.split()[0] if raw.split() else raw,
            "音标": "",
            "词性1": "",
            "释义1": head,
            "示例&短句": examples,
        }

    word = m.group("word").strip()
    first_ipa = m.group("first_ipa").strip()
    tail = (m.group("tail") or "").strip()

    ipas: list[str] = [first_ipa]
    pairs: list[tuple[str, str]] = []

    matches = list(POS_BLOCK.finditer(tail))
    if not matches:
        obj: dict[str, str] = {
            "word": word,
            "音标": first_ipa,
            "词性1": "",
            "释义1": tail,
            "示例&短句": examples,
        }
        return obj

    for i, mo in enumerate(matches):
        bracket = mo.group(1)
        pos = mo.group(2).strip()
        start = mo.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tail)
        gloss = tail[start:end].strip()
        if bracket:
            ipa = bracket.strip()
            if ipa not in ipas:
                ipas.append(ipa)
        pairs.append((pos, gloss))

    音标 = " / ".join(ipas)

    out: dict[str, str] = {
        "word": word,
        "音标": 音标,
        "示例&短句": examples,
    }
    for idx, (pos, gloss) in enumerate(pairs, start=1):
        out[f"词性{idx}"] = pos
        out[f"释义{idx}"] = gloss
    return out


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"源文件不存在: {SRC}")

    items: list[dict[str, str]] = []
    with SRC.open(encoding="utf-8", errors="replace") as f:
        for line_no, raw in enumerate(f, start=1):
            entry = parse_entry(raw)
            if entry is None:
                continue
            items.append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"写入 {OUT}，共 {len(items)} 条")


if __name__ == "__main__":
    main()
