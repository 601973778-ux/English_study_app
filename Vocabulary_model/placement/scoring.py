from __future__ import annotations

from typing import Any

from Vocabulary_model.placement.wordbank import BAND_LABEL, BAND_ORDER, BAND_TO_LEVEL

THRESHOLD = 0.6
MIN_QUESTIONS = 2
LOW_SCORE = 0.4

RECOMMEND_WORDBOOK = {
    "cet4": "cet4",
    "cet6": "cet6",
    "tem4": "tem4",
    "tem8": "tem8",
}

RECOMMEND_DAILY = {
    "cet4": 30,
    "cet6": 50,
    "tem4": 55,
    "tem8": 70,
}


def _lower_band(band: str) -> str:
    order = list(BAND_ORDER)
    try:
        i = order.index(band)
    except ValueError:
        return "cet4"
    return order[max(0, i - 1)]


def compute_result(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """answers: {band, level, correct: bool}"""
    band_totals: dict[str, int] = {b: 0 for b in BAND_ORDER}
    band_correct: dict[str, int] = {b: 0 for b in BAND_ORDER}
    raw = 0
    max_raw = 0

    for a in answers:
        band = str(a.get("band") or "cet4")
        level = int(a.get("level") or BAND_TO_LEVEL.get(band, 1))
        correct = bool(a.get("correct"))
        if band in band_totals:
            band_totals[band] += 1
            if correct:
                band_correct[band] += 1
        max_raw += level
        if correct:
            raw += level

    band_scores = {
        b: (band_correct[b] / band_totals[b] if band_totals[b] else 0.0)
        for b in BAND_ORDER
    }

    mastered = None
    for band in reversed(BAND_ORDER):
        if band_totals[band] >= MIN_QUESTIONS and band_scores[band] >= THRESHOLD:
            mastered = band
            break

    if mastered is None:
        scored = [(b, band_scores[b]) for b in BAND_ORDER if band_totals[b] > 0]
        if not scored:
            mastered = "cet4"
        else:
            best_band, best_score = max(scored, key=lambda x: x[1])
            if best_score < LOW_SCORE:
                mastered = "cet4"
            elif best_score < THRESHOLD:
                mastered = _lower_band(best_band)
            else:
                mastered = best_band

    total = len(answers)
    correct_n = sum(1 for a in answers if a.get("correct"))
    percent = round(100 * raw / max_raw) if max_raw else 0

    return {
        "mastered_band": mastered,
        "level_label": f"约{BAND_LABEL.get(mastered, mastered)}水平",
        "band_scores": {b: round(band_scores[b], 4) for b in BAND_ORDER},
        "correct": correct_n,
        "total": total,
        "percent": percent,
        "recommend_wordbook_id": RECOMMEND_WORDBOOK.get(mastered, "cet4"),
        "recommend_daily_words": RECOMMEND_DAILY.get(mastered, 50),
    }
