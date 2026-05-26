from __future__ import annotations

from urllib.parse import quote


class ServerTtsAdapter:
    """Return relative URL for existing /api/tts endpoint."""

    def tts_url_for(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        return f"/api/tts?text={quote(cleaned)}"
