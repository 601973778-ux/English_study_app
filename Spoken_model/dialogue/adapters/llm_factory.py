from __future__ import annotations

from Spoken_model.dialogue.adapters.deepseek_llm import DeepSeekLlm
from Spoken_model.dialogue.adapters.stub_llm import StubLlm
from Spoken_model.dialogue.contracts.protocols import LlmAdapter
from Spoken_model.dialogue.llm_settings import LlmSettings, load_llm_settings


def create_llm_adapter(settings: LlmSettings | None = None) -> tuple[LlmAdapter, bool, LlmSettings]:
    cfg = settings or load_llm_settings()
    if not cfg.enabled:
        return StubLlm(), False, cfg
    if not _is_configured(cfg):
        return StubLlm(), False, cfg

    provider = cfg.provider.lower()
    if provider in ("deepseek", "openai_compatible", "openai"):
        llm = DeepSeekLlm(
            base_url=cfg.base_url,
            model=cfg.model,
            api_key=cfg.api_key,
            timeout_sec=cfg.timeout_sec,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
        return llm, True, cfg

    return StubLlm(), False, cfg


def _is_configured(cfg: LlmSettings) -> bool:
    if not cfg.base_url or not cfg.model:
        return False
    if cfg.api_key:
        return True
    host = cfg.base_url.lower()
    return "127.0.0.1" in host or "localhost" in host
