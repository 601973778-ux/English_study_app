"""DeepSeek / OpenAI-compatible LLM settings for spoken dialogue."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Vocabulary_model.json_file_io import save_json_atomic

DIALOGUE_ROOT = Path(__file__).resolve().parent
DEFAULTS_FILE = DIALOGUE_ROOT / "config" / "llm_defaults.json"
USER_DATA = DIALOGUE_ROOT / "user_data"
SETTINGS_FILE = USER_DATA / "llm_settings.json"
MASK_PLACEHOLDER = "********"


@dataclass(frozen=True, slots=True)
class LlmSettings:
    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout_sec: int
    max_tokens: int
    temperature: float
    rag_min_score: float

    def to_dict(self, *, mask_secret: bool = False) -> dict[str, Any]:
        key = self.api_key
        if mask_secret and key:
            key = _mask_secret(key)
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": key,
            "timeout_sec": self.timeout_sec,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "rag_min_score": self.rag_min_score,
        }


def _mask_secret(value: str, visible: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return text[:visible] + "****"


def _load_defaults() -> dict[str, Any]:
    if not DEFAULTS_FILE.is_file():
        return {}
    return json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))


def _load_user_file() -> dict[str, Any]:
    if not SETTINGS_FILE.is_file():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _merge_settings() -> LlmSettings:
    defaults = _load_defaults()
    stored = _load_user_file()
    merged = {**defaults, **stored}

    enabled_raw = os.environ.get("DIALOGUE_LLM_ENABLED", "").strip().lower()
    if enabled_raw in ("1", "true", "yes", "on"):
        merged["enabled"] = True
    elif enabled_raw in ("0", "false", "no", "off"):
        merged["enabled"] = False

    env_key = (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if env_key:
        merged["api_key"] = env_key
    env_base = (os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "").strip()
    if env_base:
        merged["base_url"] = env_base
    env_model = (os.environ.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL") or "").strip()
    if env_model:
        merged["model"] = env_model

    return LlmSettings(
        enabled=bool(merged.get("enabled", False)),
        provider=str(merged.get("provider") or "deepseek").strip(),
        base_url=str(merged.get("base_url") or "https://api.deepseek.com/v1").strip().rstrip("/"),
        model=str(merged.get("model") or "deepseek-chat").strip(),
        api_key=str(merged.get("api_key") or "").strip(),
        timeout_sec=int(merged.get("timeout_sec") or 60),
        max_tokens=int(merged.get("max_tokens") or 256),
        temperature=float(merged.get("temperature") or 0.7),
        rag_min_score=float(merged.get("rag_min_score") or 0.0),
    )


def load_llm_settings() -> LlmSettings:
    return _merge_settings()


def get_llm_config_public() -> dict[str, Any]:
    settings = load_llm_settings()
    out = settings.to_dict(mask_secret=True)
    out["configured"] = _is_configured(settings)
    out["ready"] = settings.enabled and _is_configured(settings)
    return out


def _is_configured(settings: LlmSettings) -> bool:
    if not settings.base_url or not settings.model:
        return False
    if settings.api_key:
        return True
    host = settings.base_url.lower()
    return "127.0.0.1" in host or "localhost" in host


def save_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_llm_settings()
    api_key_in = str(payload.get("api_key") or "").strip()
    if api_key_in in ("", MASK_PLACEHOLDER):
        api_key = current.api_key
    else:
        api_key = api_key_in

    enabled = payload.get("enabled", current.enabled)
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ("1", "true", "yes", "on")

    settings = LlmSettings(
        enabled=bool(enabled),
        provider=str(payload.get("provider") or current.provider).strip(),
        base_url=str(payload.get("base_url") or current.base_url).strip().rstrip("/"),
        model=str(payload.get("model") or current.model).strip(),
        api_key=api_key,
        timeout_sec=int(payload.get("timeout_sec") or current.timeout_sec),
        max_tokens=int(payload.get("max_tokens") or current.max_tokens),
        temperature=float(payload.get("temperature") if payload.get("temperature") is not None else current.temperature),
        rag_min_score=float(
            payload.get("rag_min_score") if payload.get("rag_min_score") is not None else current.rag_min_score
        ),
    )
    USER_DATA.mkdir(parents=True, exist_ok=True)
    save_json_atomic(SETTINGS_FILE, settings.to_dict(mask_secret=False))
    return get_llm_config_public()
