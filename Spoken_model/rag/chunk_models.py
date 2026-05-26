from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Chunk:
    chunk_id: str
    chunk_type: str
    corpus_id: str
    source_id: str
    topic_id: int
    topic_title_en: str
    topic_title_zh: str
    text_en: str
    text_zh: str
    text_for_embedding: str
    scenario_tags: list[str] = field(default_factory=list)
    dialogue_id: str = ""
    turn_index: int = 0
    speaker: str = ""
    source_file: str = ""
    source_line: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def is_primarily_english(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return False
    cjk = len(_CJK_RE.findall(clean))
    latin = len(_LATIN_RE.findall(clean))
    return latin > 0 and cjk <= max(2, latin // 4)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def strip_list_marker(text: str) -> str:
    return re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩\d+\.\s]+", "", text.strip())


def tokenize(text: str) -> list[str]:
    lowered = (text or "").lower()
    return _TOKEN_RE.findall(lowered)


def build_embedding_text(
    *,
    chunk_type: str,
    topic_title_en: str,
    topic_title_zh: str,
    text_en: str,
    text_zh: str,
    scenario_tags: Iterable[str],
) -> str:
    tags = " ".join(scenario_tags)
    return normalize_ws(
        f"topic {topic_title_en} {topic_title_zh} "
        f"type {chunk_type} tags {tags} "
        f"en {text_en} zh {text_zh}"
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count
