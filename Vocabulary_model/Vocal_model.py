from __future__ import annotations

import base64
import datetime as dt
import hmac
import hashlib
import json
import os
import urllib.parse
from dataclasses import dataclass
from email.utils import format_datetime


class XfyunTtsError(RuntimeError):
    pass


# 控制台「在线语音合成」里常见默认可用；x4_enus_* 需在「发音人授权」单独开通，否则会 11200 licc failed
DEFAULT_TTS_VCN = "x4_xiaoyan"
FALLBACK_TTS_VCN = "xiaoyan"


@dataclass(frozen=True, slots=True)
class XfyunCredentials:
    appid: str
    api_key: str
    api_secret: str

    @staticmethod
    def from_env() -> "XfyunCredentials":
        appid = (os.environ.get("XFYUN_APPID") or "").strip()
        api_key = (os.environ.get("XFYUN_API_KEY") or "").strip()
        api_secret = (os.environ.get("XFYUN_API_SECRET") or "").strip()
        if not appid or not api_key or not api_secret:
            raise XfyunTtsError(
                "未配置讯飞凭证。请在「API 接入配置」页面填写，"
                "或设置环境变量 XFYUN_APPID、XFYUN_API_KEY、XFYUN_API_SECRET。"
            )
        return XfyunCredentials(appid=appid, api_key=api_key, api_secret=api_secret)


def load_xfyun_credentials() -> XfyunCredentials:
    from Vocabulary_model.xfyun_credentials_store import resolve_xfyun_credentials

    try:
        stored = resolve_xfyun_credentials()
    except RuntimeError as e:
        raise XfyunTtsError(str(e)) from e
    return XfyunCredentials(
        appid=stored.appid, api_key=stored.api_key, api_secret=stored.api_secret
    )


def _b64_text(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _hmac_sha256_base64(text: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _build_ws_url(creds: XfyunCredentials) -> str:
    host = "tts-api.xfyun.cn"
    path = "/v2/tts"
    request_line = f"GET {path} HTTP/1.1"
    date = format_datetime(dt.datetime.now(dt.timezone.utc), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
    signature = _hmac_sha256_base64(signature_origin, creds.api_secret)
    authorization_origin = (
        f'api_key="{creds.api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urllib.parse.urlencode(
        {
            "authorization": authorization,
            "date": date,
            "host": host,
        }
    )
    return f"wss://{host}{path}?{query}"


def _tts_error_message(code: int, raw_message: str) -> str:
    msg = str(raw_message or "").strip()
    if code == 11200 or "licc" in msg.lower():
        return (
            "TTS failed: 11200 发音人/服务未授权（licc failed）。"
            "请到讯飞控制台 → 在线语音合成 → 发音人授权管理，"
            f"添加并开通发音人（推荐试用 {DEFAULT_TTS_VCN}），"
            "确认本应用的 APPID 已开通「在线语音合成」且用量未超限。"
            f" 原始信息: {msg or code}"
        )
    if code == 10005:
        return (
            "TTS failed: 10005 appid 授权失败，请核对 APPID 与 API Key/Secret 是否同一应用。"
            f" 原始信息: {msg or code}"
        )
    return f"TTS failed: {code} {msg}".strip()


def _resolve_voice_name(explicit: str | None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    env_vcn = (os.environ.get("XFYUN_VCN") or "").strip()
    if env_vcn:
        return env_vcn
    try:
        from Vocabulary_model.xfyun_credentials_store import load_tts_voice

        return load_tts_voice()
    except Exception:
        return DEFAULT_TTS_VCN


def synthesize_english_word(
    text: str,
    *,
    voice_name: str | None = None,
    aue: str = "lame",
    auf: str = "audio/L16;rate=16000",
    speed: int = 50,
    volume: int = 50,
    pitch: int = 50,
    timeout_s: float = 12.0,
) -> tuple[bytes, str]:
    """
    Call XFYUN Online TTS (WebSocket v2).
    Returns: (audio_bytes, content_type)

    Notes:
    - credentials are read from environment variables, never from code.
    - this uses official v2 websocket auth with api_key + api_secret.
    """
    try:
        from websocket import create_connection
    except Exception as e:  # noqa: BLE001
        raise XfyunTtsError(
            "Missing dependency websocket-client. Install with: pip install websocket-client"
        ) from e

    word = (text or "").strip()
    if not word:
        raise XfyunTtsError("empty text")
    if len(word) > 64:
        raise XfyunTtsError("text too long")

    creds = load_xfyun_credentials()
    ws_url = _build_ws_url(creds)
    vcn_primary = _resolve_voice_name(voice_name)
    vcn_candidates = []
    for v in (vcn_primary, DEFAULT_TTS_VCN, FALLBACK_TTS_VCN):
        if v and v not in vcn_candidates:
            vcn_candidates.append(v)

    last_err: XfyunTtsError | None = None
    for vcn in vcn_candidates:
        business: dict[str, object] = {
            "aue": aue,
            "auf": auf,
            "vcn": vcn,
            "speed": int(speed),
            "volume": int(volume),
            "pitch": int(pitch),
            "tte": "UTF8",
            "reg": "2",
        }
        if aue == "lame":
            business["sfl"] = 1

        payload = {
            "common": {"app_id": creds.appid},
            "business": business,
            "data": {
                "status": 2,
                "text": _b64_text(word),
            },
        }

        audio_chunks: list[bytes] = []
        ws = None
        try:
            ws = create_connection(ws_url, timeout=timeout_s)
            ws.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = ws.recv()
                if not raw:
                    continue
                msg = json.loads(raw)
                code = int(msg.get("code", -1))
                if code != 0:
                    raise XfyunTtsError(
                        _tts_error_message(code, str(msg.get("message", "")))
                    )
                data = msg.get("data") or {}
                audio_b64 = data.get("audio")
                if audio_b64:
                    audio_chunks.append(base64.b64decode(audio_b64))
                if int(data.get("status", 0)) == 2:
                    break
            audio = b"".join(audio_chunks)
            if not audio:
                raise XfyunTtsError("empty audio from TTS")
            content_type = "audio/mpeg" if aue == "lame" else "application/octet-stream"
            return audio, content_type
        except XfyunTtsError as e:
            last_err = e
            err_text = str(e)
            if "11200" not in err_text and "licc" not in err_text.lower():
                raise
            continue
        except Exception as e:  # noqa: BLE001
            raise XfyunTtsError(str(e)) from e
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    if last_err is not None:
        raise last_err
    raise XfyunTtsError("TTS failed: no voice available")

