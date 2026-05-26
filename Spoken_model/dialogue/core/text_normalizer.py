from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def normalize_user_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = _WS_RE.sub(" ", cleaned)
    return cleaned


def token_set(text: str) -> set[str]:
    lowered = normalize_user_text(text).lower()
    return {t for t in re.findall(r"[a-z0-9']+", lowered) if t}
