from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from Spoken_model.dialogue.contracts.types import SessionState
from Spoken_model.dialogue.core.text_normalizer import normalize_user_text
from Spoken_model.dialogue.scenarios.loader import _match_patterns

_DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "quick_chitchat.json"


class QuickChitchatEngine:
    """Pattern-matched short replies (hello, thanks, etc.) without script engine or LLM."""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or _DEFAULT_DATA
        raw = {}
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                raw = loaded
        self._rules: list[dict[str, Any]] = list(raw.get("rules") or [])

    def try_reply(self, user_text: str, session: SessionState) -> str | None:
        text = normalize_user_text(user_text)
        if not text:
            return None
        for rule in self._rules:
            patterns = rule.get("patterns") or []
            if not _match_patterns(text, patterns):
                continue
            replies = rule.get("replies") or []
            single = rule.get("reply")
            pool = [str(r).strip() for r in replies if str(r).strip()]
            if single and str(single).strip():
                pool.append(str(single).strip())
            if not pool:
                continue
            return random.choice(pool)
        return None
