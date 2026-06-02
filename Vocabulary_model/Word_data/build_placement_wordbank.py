#!/usr/bin/env python3
"""
从 CET4 / CET6 / 专业四八级词表构建「词汇水平评估」抽样词库。

分层原则（难度递增）：
- 四级：仅在 CET4 词表、不在 CET6 词表
- 六级：仅在 CET6 词表、不在 CET4 词表
- 专业四级：在专业四八级总表、但不在 CET4∪CET6、且不在专八星标表
- 专业八级：在专八星标词表、且不在 CET4∪CET6

输出：Word_data/placement_assessment_words.json
字段：word, meaning, source, band, level
"""

from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORD_DATA = Path(__file__).resolve().parent
WL = ROOT / "english-wordlists-master" / "english-wordlists-master"

sys.path.insert(0, str(ROOT / "Vocabulary_model" / "Word_data"))
from convert_edited_txt import parse_entry as parse_cet6_line  # noqa: E402

PER_BAND = 50
SEED = 20260520
OUT = WORD_DATA / "placement_assessment_words.json"

POS_TAIL = re.compile(
    r"^(?:n\.|v\.|adj\.|adv\.|a\.|prep\.|conj\.|pron\.|vt\.|vi\.|art\.|int\.|num\.|aux\.|det\.)\s*",
    re.I,
)
TEM_HEAD = re.compile(
    r"^\*?(?P<word>[A-Za-z][A-Za-z' -]*?)\s+(?:\[[^\]]+\]\s*)?(?P<tail>.+)$"
)
CET4_HEAD = re.compile(r"^(?P<word>[A-Za-z][A-Za-z'-]*)\s+(?P<tail>.+)$")
SKIP_LINE = re.compile(
    r"^(大学英语|共\s*\d+|[$A-Z]$|\([共\d].*)",
)


@dataclass(frozen=True)
class WordItem:
    word: str
    meaning: str

    @property
    def key(self) -> str:
        return self.word.casefold()


def _clean_meaning(text: str) -> str:
    s = str(text or "").strip()
    s = re.sub(r"^\d+\.\s*", "", s)
    s = POS_TAIL.sub("", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace("；", "；").strip(" ;，,")
    return s[:120] if len(s) > 120 else s


def _meaning_from_pairs(entry: dict[str, str]) -> str:
    for i in range(1, 12):
        g = entry.get(f"释义{i}", "")
        if str(g).strip():
            return _clean_meaning(str(g))
    return _clean_meaning(entry.get("word", ""))


def load_cet4() -> dict[str, WordItem]:
    path = WL / "CET4_edited.txt"
    out: dict[str, WordItem] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or SKIP_LINE.match(line):
            continue
        if len(line) == 1 and line.isalpha():
            continue
        m = CET4_HEAD.match(line)
        if not m:
            continue
        word = m.group("word").strip()
        tail = m.group("tail").strip()
        gloss = re.sub(r"^\[[^\]]+\]\s*", "", tail)
        gloss = POS_TAIL.sub("", gloss).strip()
        if not word or not gloss:
            continue
        item = WordItem(word=word, meaning=_clean_meaning(gloss))
        out[item.key] = item
    return out


def load_cet6_json() -> dict[str, WordItem]:
    path = WORD_DATA / "CET6_edited.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, WordItem] = {}
    for row in data:
        w = str(row.get("word", "")).strip()
        if not w:
            continue
        meaning = _meaning_from_pairs(row)
        if not meaning:
            continue
        item = WordItem(word=w, meaning=meaning)
        out[item.key] = item
    return out


def load_tem_line_dict(path: Path) -> dict[str, WordItem]:
    out: dict[str, WordItem] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("("):
            continue
        m = TEM_HEAD.match(line)
        if not m:
            continue
        word = m.group("word").strip().replace("  ", " ")
        if not word or word.lower() in {"a", "an"}:
            continue
        tail = m.group("tail").strip()
        tail = re.sub(r"^\[[^\]]+\]\s*", "", tail)
        tail = POS_TAIL.sub("", tail).strip()
        tail = re.sub(r"^\d+\.\s*", "", tail)
        if not tail:
            continue
        item = WordItem(word=word, meaning=_clean_meaning(tail))
        out[item.key] = item
    return out


def sample_items(pool: dict[str, WordItem], n: int, rng: random.Random) -> list[WordItem]:
    keys = sorted(pool.keys())
    if len(keys) <= n:
        return [pool[k] for k in keys]
    return [pool[k] for k in rng.sample(keys, n)]


def build_pools(
    cet4: dict[str, WordItem],
    cet6: dict[str, WordItem],
    tem_all: dict[str, WordItem],
    tem8: dict[str, WordItem],
) -> dict[str, list[WordItem]]:
    k4 = set(cet4)
    k6 = set(cet6)
    k8 = set(tem8)
    lower = k4 | k6

    pool_cet4 = {k: cet4[k] for k in k4 - k6}
    pool_cet6 = {k: cet6[k] for k in k6 - k4}
    pool_tem8 = {k: tem8[k] for k in k8 - lower}
    pool_tem4 = {
        k: tem_all[k]
        for k in tem_all
        if k not in lower and k not in k8
    }

    # 若差集不足，按难度降级补充（仍保持标签，尽量不与高阶重复）
    rng = random.Random(SEED)

    def fill(pool: dict[str, WordItem], fallback: dict[str, WordItem], n: int) -> list[WordItem]:
        picked = sample_items(pool, n, rng)
        if len(picked) >= n:
            return picked[:n]
        used = {x.key for x in picked}
        extra_keys = [k for k in sorted(fallback) if k not in used and k not in pool]
        rng.shuffle(extra_keys)
        for k in extra_keys:
            if len(picked) >= n:
                break
            picked.append(fallback[k])
        return picked[:n]

    return {
        "cet4": fill(pool_cet4, cet4, PER_BAND),
        "cet6": fill(pool_cet6, cet6, PER_BAND),
        "tem4": fill(pool_tem4, {k: tem_all[k] for k in tem_all if k not in lower}, PER_BAND),
        "tem8": fill(pool_tem8, tem8, PER_BAND),
    }


def main() -> None:
    cet4 = load_cet4()
    cet6 = load_cet6_json()
    tem_all = load_tem_line_dict(WL / "英语专业四八级词汇表.txt")
    tem8 = load_tem_line_dict(WL / "英语专业星标八级词汇.txt")

    pools = build_pools(cet4, cet6, tem_all, tem8)

    meta = [
        ("cet4", "四级", 1),
        ("cet6", "六级", 2),
        ("tem4", "专业四级", 3),
        ("tem8", "专业八级", 4),
    ]

    items: list[dict] = []
    stats: dict[str, int] = {}
    for band, source, level in meta:
        band_items = pools[band]
        stats[band] = len(band_items)
        for it in band_items:
            items.append(
                {
                    "word": it.word,
                    "meaning": it.meaning,
                    "source": source,
                    "band": band,
                    "level": level,
                }
            )

    payload = {
        "version": 1,
        "description": "词汇水平快测抽样词库：四级→六级→专业四级→专业八级，难度递增",
        "per_band": PER_BAND,
        "total": len(items),
        "bands": [
            {"band": b, "source": s, "level": lv, "count": stats[b]}
            for b, s, lv in meta
        ],
        "items": items,
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(items)} items)")
    for b, s, _ in meta:
        print(f"  {s} ({b}): {stats[b]}")


if __name__ == "__main__":
    main()
