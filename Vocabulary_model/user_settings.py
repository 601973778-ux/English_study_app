from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path(__file__).resolve().parent / "user_settings.json"
VALID_REVIEW_RATIOS = {"1:1", "1:2", "1:3", "1:4"}
DEFAULT_SETTINGS = {
    "daily_words": 50,
    "review_ratio": "1:1",
    "similar_words_auto_load": False,
    "wordbook_id": "cet6",
}


def _normalize_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_SETTINGS)

    daily_words_raw = raw.get("daily_words", DEFAULT_SETTINGS["daily_words"])
    review_ratio_raw = raw.get("review_ratio", DEFAULT_SETTINGS["review_ratio"])
    auto_similar_raw = raw.get(
        "similar_words_auto_load", DEFAULT_SETTINGS["similar_words_auto_load"]
    )
    wordbook_raw = raw.get("wordbook_id", DEFAULT_SETTINGS["wordbook_id"])

    try:
        daily_words = int(daily_words_raw)
    except (TypeError, ValueError):
        daily_words = int(DEFAULT_SETTINGS["daily_words"])

    if daily_words < 1:
        daily_words = 1
    if daily_words > 500:
        daily_words = 500

    review_ratio = str(review_ratio_raw)
    if review_ratio not in VALID_REVIEW_RATIOS:
        review_ratio = str(DEFAULT_SETTINGS["review_ratio"])

    if isinstance(auto_similar_raw, bool):
        similar_words_auto_load = auto_similar_raw
    elif isinstance(auto_similar_raw, (int, float)):
        similar_words_auto_load = bool(auto_similar_raw)
    elif isinstance(auto_similar_raw, str):
        similar_words_auto_load = auto_similar_raw.strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    else:
        similar_words_auto_load = bool(DEFAULT_SETTINGS["similar_words_auto_load"])

    from Vocabulary_model.wordbook_catalog import normalize_wordbook_id

    wordbook_id = normalize_wordbook_id(str(wordbook_raw))

    return {
        "daily_words": daily_words,
        "review_ratio": review_ratio,
        "similar_words_auto_load": similar_words_auto_load,
        "wordbook_id": wordbook_id,
    }


def load_user_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)
    normalized = _normalize_settings(data)
    raw_wb = str(data.get("wordbook_id", "")).strip().lower()
    if raw_wb and raw_wb != str(normalized.get("wordbook_id", "")).strip().lower():
        SETTINGS_FILE.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return normalized


def save_user_settings(raw: Any) -> dict[str, Any]:
    prev = load_user_settings()
    if not isinstance(raw, dict):
        raw = {}
    merged = {**prev, **raw}
    settings = _normalize_settings(merged)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings

