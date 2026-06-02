from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_CONFIG = Path(__file__).resolve().parent / "config" / "dialogue_flags.json"


@lru_cache(maxsize=1)
def load_dialogue_flags() -> dict:
    if _CONFIG.is_file():
        with open(_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    return {}


def is_script_engine_frozen() -> bool:
    """True → pipeline skips ScriptEngine; uses quick chitchat + RAG/LLM only."""
    env = os.environ.get("DIALOGUE_SCRIPT_FROZEN")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(load_dialogue_flags().get("script_engine_frozen", False))
