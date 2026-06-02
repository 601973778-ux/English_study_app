from __future__ import annotations

import os

from Spoken_model.dialogue.adapters.passthrough_asr import PassthroughAsr
from Spoken_model.dialogue.adapters.xfyun_iat_asr import XfyunIatAsr
from Spoken_model.dialogue.contracts.protocols import AsrAdapter


def create_asr_adapter() -> AsrAdapter:
    backend = (os.environ.get("DIALOGUE_ASR") or "xfyun").strip().lower()
    if backend in {"passthrough", "none", "off"}:
        return PassthroughAsr()
    return XfyunIatAsr()
