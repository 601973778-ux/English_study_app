from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORD_BANK_PATH = Path(__file__).resolve().parents[1] / "Word_data" / "placement_assessment_words.json"

BAND_ORDER = ("cet4", "cet6", "tem4", "tem8")
BAND_TO_LEVEL = {"cet4": 1, "cet6": 2, "tem4": 3, "tem8": 4}
LEVEL_TO_BAND = {1: "cet4", 2: "cet6", 3: "tem4", 4: "tem8"}
BAND_LABEL = {
    "cet4": "四级",
    "cet6": "六级",
    "tem4": "专业四级",
    "tem8": "专业八级",
}


@dataclass(frozen=True)
class PlacementWord:
    word: str
    meaning: str
    source: str
    band: str
    level: int


def load_wordbank(path: Path | None = None) -> list[PlacementWord]:
    p = path or WORD_BANK_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    items = raw.get("items") or []
    out: list[PlacementWord] = []
    for row in items:
        w = str(row.get("word") or "").strip()
        if not w:
            continue
        band = str(row.get("band") or "cet4").strip().lower()
        out.append(
            PlacementWord(
                word=w,
                meaning=str(row.get("meaning") or "").strip(),
                source=str(row.get("source") or BAND_LABEL.get(band, band)),
                band=band,
                level=int(row.get("level") or BAND_TO_LEVEL.get(band, 1)),
            )
        )
    return out


def words_by_band(words: list[PlacementWord]) -> dict[str, list[PlacementWord]]:
    buckets: dict[str, list[PlacementWord]] = {b: [] for b in BAND_ORDER}
    for w in words:
        if w.band in buckets:
            buckets[w.band].append(w)
    return buckets


def pick_words(
    pool: list[PlacementWord],
    n: int,
    rng: random.Random,
    *,
    exclude: set[str],
) -> list[PlacementWord]:
    candidates = [w for w in pool if w.word.casefold() not in exclude]
    if len(candidates) <= n:
        return list(candidates)
    return rng.sample(candidates, n)
