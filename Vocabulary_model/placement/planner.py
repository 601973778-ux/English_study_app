from __future__ import annotations

import random
from typing import Any

from Vocabulary_model.placement.wordbank import (
    LEVEL_TO_BAND,
    PlacementWord,
    pick_words,
    words_by_band,
)


def _band_at_level(level: int) -> str:
    return LEVEL_TO_BAND[max(1, min(4, level))]


def plan_probe(rng: random.Random, buckets: dict[str, list[PlacementWord]], used: set[str]) -> list[PlacementWord]:
    return pick_words(buckets["cet6"], 2, rng, exclude=used)


def cursor_after_probe(probe_correct: int) -> int:
    if probe_correct <= 0:
        return 1
    if probe_correct == 1:
        return 2
    return 3


def adjust_cursor_after_main(cursor: int, main_correct: int) -> int:
    if main_correct >= 2:
        return min(4, cursor + 1)
    if main_correct <= 0:
        return max(1, cursor - 1)
    return cursor


def plan_main(cursor: int, rng: random.Random, buckets: dict[str, list[PlacementWord]], used: set[str]) -> list[PlacementWord]:
    band = _band_at_level(cursor)
    return pick_words(buckets.get(band, []), 3, rng, exclude=used)


def plan_adjacent(
    cursor: int,
    main_correct: int,
    rng: random.Random,
    buckets: dict[str, list[PlacementWord]],
    used: set[str],
) -> list[PlacementWord]:
    if main_correct >= 2:
        level = min(4, cursor + 1)
        return pick_words(buckets.get(_band_at_level(level), []), 2, rng, exclude=used)
    if main_correct <= 0:
        level = max(1, cursor - 1)
        return pick_words(buckets.get(_band_at_level(level), []), 2, rng, exclude=used)
    low = pick_words(buckets.get(_band_at_level(cursor), []), 1, rng, exclude=used)
    used.update(w.word.casefold() for w in low)
    high_level = max(1, cursor - 1)
    high = pick_words(buckets.get(_band_at_level(high_level), []), 1, rng, exclude=used)
    return low + high


def estimate_candidate_band(answers: list[dict[str, Any]]) -> str:
    from Vocabulary_model.placement.scoring import MIN_QUESTIONS, THRESHOLD

    band_totals: dict[str, int] = {}
    band_correct: dict[str, int] = {}
    for a in answers:
        b = str(a.get("band") or "cet4")
        band_totals[b] = band_totals.get(b, 0) + 1
        if a.get("correct"):
            band_correct[b] = band_correct.get(b, 0) + 1
    for band in ("tem8", "tem4", "cet6", "cet4"):
        t = band_totals.get(band, 0)
        if t >= MIN_QUESTIONS:
            if band_correct.get(band, 0) / t >= THRESHOLD:
                return band
        elif t > 0 and band_correct.get(band, 0) == t:
            return band
    if answers:
        return str(answers[-1].get("band") or "cet6")
    return "cet6"


def plan_confirm(
    candidate: str,
    rng: random.Random,
    buckets: dict[str, list[PlacementWord]],
    used: set[str],
) -> list[PlacementWord]:
    order = ("cet4", "cet6", "tem4", "tem8")
    try:
        idx = order.index(candidate)
    except ValueError:
        idx = 1
    high_band = order[min(len(order) - 1, idx + 1)] if candidate != "tem8" else "tem8"
    part_a = pick_words(buckets.get(candidate, []), 2, rng, exclude=used)
    used.update(w.word.casefold() for w in part_a)
    part_b = pick_words(buckets.get(high_band, []), 1, rng, exclude=used)
    return part_a + part_b
