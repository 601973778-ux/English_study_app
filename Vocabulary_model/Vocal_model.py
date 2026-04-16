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
                "Missing XFYUN credentials. Set env vars "
                "XFYUN_APPID, XFYUN_API_KEY and XFYUN_API_SECRET."
            )
        return XfyunCredentials(appid=appid, api_key=api_key, api_secret=api_secret)


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


def synthesize_english_word(
    text: str,
    *,
    voice_name: str = "x4_enus_luna_assist",
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

    creds = XfyunCredentials.from_env()
    ws_url = _build_ws_url(creds)

    business: dict[str, object] = {
        "aue": aue,
        "auf": auf,
        "vcn": voice_name,
        "speed": int(speed),
        "volume": int(volume),
        "pitch": int(pitch),
        "tte": "UTF8",
        "reg": "0",
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
                raise XfyunTtsError(f"TTS failed: {code} {msg.get('message', '')}")
            data = msg.get("data") or {}
            audio_b64 = data.get("audio")
            if audio_b64:
                audio_chunks.append(base64.b64decode(audio_b64))
            if int(data.get("status", 0)) == 2:
                break
    except XfyunTtsError:
        raise
    except Exception as e:  # noqa: BLE001
        raise XfyunTtsError(str(e)) from e
    finally:
        try:
            ws.close()  # type: ignore[name-defined]
        except Exception:
            pass

    audio = b"".join(audio_chunks)
    if not audio:
        raise XfyunTtsError("empty audio from TTS")

    content_type = "audio/mpeg" if aue == "lame" else "application/octet-stream"
    return audio, content_type

