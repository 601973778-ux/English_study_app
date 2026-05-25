"""讯飞 TTS 凭证：本地 JSON（优先于环境变量）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Vocabulary_model.json_file_io import save_json_atomic


@dataclass(frozen=True, slots=True)
class StoredXfyunCredentials:
    appid: str
    api_key: str
    api_secret: str

DATA_DIR = Path(__file__).resolve().parent / "user_data"
CREDENTIALS_FILE = DATA_DIR / "xfyun_credentials.json"
FILE_VERSION = 1
MASK_PLACEHOLDER = "********"
DEFAULT_TTS_VCN = "x4_xiaoyan"


def _mask_secret(value: str, visible: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return text[:visible] + "****"


def _load_file() -> dict[str, Any] | None:
    if not CREDENTIALS_FILE.is_file():
        return None
    try:
        import json

        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _from_env() -> StoredXfyunCredentials | None:
    appid = (os.environ.get("XFYUN_APPID") or "").strip()
    api_key = (os.environ.get("XFYUN_API_KEY") or "").strip()
    api_secret = (os.environ.get("XFYUN_API_SECRET") or "").strip()
    if not appid or not api_key or not api_secret:
        return None
    return StoredXfyunCredentials(appid=appid, api_key=api_key, api_secret=api_secret)


def _from_file() -> StoredXfyunCredentials | None:
    data = _load_file()
    if not data:
        return None
    appid = str(data.get("appid", "")).strip()
    api_key = str(data.get("api_key", "")).strip()
    api_secret = str(data.get("api_secret", "")).strip()
    if not appid or not api_key or not api_secret:
        return None
    return StoredXfyunCredentials(appid=appid, api_key=api_key, api_secret=api_secret)


def load_tts_voice() -> str:
    data = _load_file() or {}
    vcn = str(data.get("vcn", "")).strip()
    if vcn:
        return vcn
    env_vcn = (os.environ.get("XFYUN_VCN") or "").strip()
    return env_vcn or DEFAULT_TTS_VCN


def resolve_xfyun_credentials() -> StoredXfyunCredentials:
    creds = _from_file() or _from_env()
    if creds is not None:
        return creds
    raise RuntimeError(
        "未配置讯飞 TTS。请在浏览器打开「API 接入配置」填写，"
        "或设置环境变量 XFYUN_APPID / XFYUN_API_KEY / XFYUN_API_SECRET。"
    )


def get_tts_config_public() -> dict[str, Any]:
    file_data = _load_file() or {}
    file_creds = _from_file()
    env_creds = _from_env()
    configured = file_creds is not None or env_creds is not None
    if file_creds is not None:
        source = "file"
        active = file_creds
    elif env_creds is not None:
        source = "env"
        active = env_creds
    else:
        source = "none"
        active = None

    return {
        "configured": configured,
        "source": source,
        "storage_file": str(CREDENTIALS_FILE),
        "appid": str(active.appid) if active else str(file_data.get("appid", "")).strip(),
        "api_key_masked": _mask_secret(active.api_key if active else file_data.get("api_key", "")),
        "has_api_key": bool(
            str(file_data.get("api_key", "")).strip()
            or (env_creds is not None and file_creds is None)
        ),
        "has_api_secret": bool(
            str(file_data.get("api_secret", "")).strip()
            or (env_creds is not None and file_creds is None)
        ),
        "file_has_priority": file_creds is not None,
        "env_also_set": env_creds is not None,
        "vcn": load_tts_voice(),
        "vcn_hint": (
            "默认 x4_xiaoyan（需在控制台开通）。若 11200 licc failed，"
            "请到「在线语音合成 → 发音人授权管理」添加该发音人。"
        ),
    }


def save_tts_config(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("clear"):
        if CREDENTIALS_FILE.is_file():
            CREDENTIALS_FILE.unlink()
        return get_tts_config_public()

    existing = _load_file() or {}
    appid = str(payload.get("appid", existing.get("appid", ""))).strip()
    api_key_in = str(payload.get("api_key", "")).strip()
    api_secret_in = str(payload.get("api_secret", "")).strip()

    api_key = existing.get("api_key", "")
    if api_key_in and api_key_in not in (MASK_PLACEHOLDER,) and not api_key_in.endswith("****"):
        api_key = api_key_in

    api_secret = existing.get("api_secret", "")
    if api_secret_in and api_secret_in != MASK_PLACEHOLDER:
        api_secret = api_secret_in

    if not appid or not api_key or not api_secret:
        raise ValueError("请填写完整的 APPID、API Key 与 API Secret")

    vcn_in = str(payload.get("vcn", existing.get("vcn", ""))).strip()
    vcn = vcn_in or DEFAULT_TTS_VCN

    save_json_atomic(
        CREDENTIALS_FILE,
        {
            "version": FILE_VERSION,
            "appid": appid,
            "api_key": api_key,
            "api_secret": api_secret,
            "vcn": vcn,
        },
    )
    return get_tts_config_public()
