from __future__ import annotations

from Spoken_model.dialogue.contracts.protocols import AsrAdapter


class PassthroughAsr:
    """Development ASR: caller must supply user_text; audio triggers NotImplemented."""

    def transcribe(
        self,
        audio: bytes,
        *,
        language: str = "en",
        audio_format: str | None = "pcm_s16le",
    ) -> str:
        if not audio:
            return ""
        raise NotImplementedError(
            "ASR not configured. Send user_text, or set DIALOGUE_ASR=xfyun with XFYUN credentials."
        )
