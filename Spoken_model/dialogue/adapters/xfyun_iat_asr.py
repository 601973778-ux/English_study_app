from __future__ import annotations

import base64
import datetime as dt
import hmac
import hashlib
import json
import urllib.parse
from email.utils import format_datetime

from Vocabulary_model.Vocal_model import XfyunCredentials, XfyunTtsError, load_xfyun_credentials
from Spoken_model.dialogue.adapters.audio_converter import XfyunAsrError, to_pcm_s16le_16k

_IAT_HOST = "iat-api.xfyun.cn"
_IAT_PATH = "/v2/iat"
_FRAME_SIZE = 1280


def _hmac_sha256_base64(text: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _build_iat_ws_url(creds: XfyunCredentials) -> str:
    request_line = f"GET {_IAT_PATH} HTTP/1.1"
    date = format_datetime(dt.datetime.now(dt.timezone.utc), usegmt=True)
    signature_origin = f"host: {_IAT_HOST}\ndate: {date}\n{request_line}"
    signature = _hmac_sha256_base64(signature_origin, creds.api_secret)
    authorization_origin = (
        f'api_key="{creds.api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urllib.parse.urlencode(
        {"authorization": authorization, "date": date, "host": _IAT_HOST}
    )
    return f"wss://{_IAT_HOST}{_IAT_PATH}?{query}"


def _business_params(language: str) -> dict[str, object]:
    lang = (language or "en").strip().lower()
    if lang.startswith("zh"):
        return {"language": "zh_cn", "domain": "iat", "accent": "mandarin", "vad_eos": 3000}
    return {"language": "en_us", "domain": "iat", "accent": "mandarin", "vad_eos": 3000}


def _parse_iat_text(result: dict) -> str:
    parts: list[str] = []
    for ws in result.get("ws") or []:
        for cw in ws.get("cw") or []:
            word = str(cw.get("w") or "")
            if word:
                parts.append(word)
    return "".join(parts)


def _chunk_pcm(pcm: bytes, frame_size: int = _FRAME_SIZE) -> list[tuple[bytes, int]]:
    if not pcm:
        return []
    chunks = [pcm[i : i + frame_size] for i in range(0, len(pcm), frame_size)]
    if len(chunks) == 1:
        return [(chunks[0], 2)]
    framed: list[tuple[bytes, int]] = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            framed.append((chunk, 0))
        elif idx == len(chunks) - 1:
            framed.append((chunk, 2))
        else:
            framed.append((chunk, 1))
    return framed


class XfyunIatAsr:
    """XFYUN 语音听写 IAT (WebSocket v2)."""

    def transcribe(
        self,
        audio: bytes,
        *,
        language: str = "en",
        audio_format: str | None = "pcm_s16le",
    ) -> str:
        if not audio:
            return ""
        try:
            from websocket import create_connection
        except Exception as e:  # noqa: BLE001
            raise XfyunAsrError(
                "缺少依赖 websocket-client。请执行: pip install websocket-client"
            ) from e

        pcm = to_pcm_s16le_16k(audio, audio_format)
        try:
            creds = load_xfyun_credentials()
        except XfyunTtsError as e:
            raise XfyunAsrError(str(e)) from e
        ws_url = _build_iat_ws_url(creds)
        business = _business_params(language)
        frames = _chunk_pcm(pcm)
        if not frames:
            raise XfyunAsrError("empty audio after conversion")

        texts: list[str] = []
        ws = None
        try:
            ws = create_connection(ws_url, timeout=20.0)
            for idx, (chunk, status) in enumerate(frames):
                data = {
                    "status": status,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                }
                if idx == 0:
                    payload = {
                        "common": {"app_id": creds.appid},
                        "business": business,
                        "data": data,
                    }
                else:
                    payload = {"data": data}
                ws.send(json.dumps(payload, ensure_ascii=False))

            while True:
                raw = ws.recv()
                if not raw:
                    continue
                msg = json.loads(raw)
                code = int(msg.get("code", -1))
                if code != 0:
                    raise XfyunAsrError(
                        f"ASR failed: {code} {str(msg.get('message') or '').strip()}".strip()
                    )
                data = msg.get("data") or {}
                result = data.get("result")
                if isinstance(result, dict):
                    piece = _parse_iat_text(result)
                    if piece:
                        texts.append(piece)
                if int(data.get("status", 0)) == 2:
                    break
        except XfyunAsrError:
            raise
        except Exception as e:  # noqa: BLE001
            raise XfyunAsrError(str(e)) from e
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        text = "".join(texts).strip()
        if not text:
            raise XfyunAsrError("ASR returned empty text")
        return text
