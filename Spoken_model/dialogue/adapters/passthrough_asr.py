from __future__ import annotations

from Spoken_model.dialogue.contracts.protocols import AsrAdapter


class PassthroughAsr:
    """Development ASR: caller must supply user_text; audio triggers NotImplemented."""

    def transcribe(self, audio: bytes, *, language: str = "en") -> str:
        if not audio:
            return ""
        raise NotImplementedError(
            "ASR not configured yet. Send user_text in the turn request, "
            "or wire Xfyun IAT via AsrAdapter later."
        )
