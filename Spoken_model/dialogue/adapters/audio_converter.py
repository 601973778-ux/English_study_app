from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_PCM_ALIASES = frozenset({"pcm", "pcm_s16le", "raw", "s16le", "l16"})


class XfyunAsrError(RuntimeError):
    pass


def to_pcm_s16le_16k(audio: bytes, audio_format: str | None) -> bytes:
    if not audio:
        raise XfyunAsrError("empty audio")
    fmt = (audio_format or "pcm_s16le").strip().lower()
    if fmt in _PCM_ALIASES:
        return audio

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise XfyunAsrError(
            "当前音频格式需要 ffmpeg 转 PCM。请安装 ffmpeg 并加入 PATH，"
            "或让前端上传 audio_format=pcm_s16le。"
        )

    suffix = {
        "webm": ".webm",
        "ogg": ".ogg",
        "wav": ".wav",
        "mp3": ".mp3",
        "m4a": ".m4a",
        "mp4": ".mp4",
    }.get(fmt, f".{fmt}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as inp:
        inp.write(audio)
        inp_path = Path(inp.name)
    out_path = inp_path.with_suffix(".pcm")
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(inp_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                str(out_path),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]
            raise XfyunAsrError(f"ffmpeg 转码失败: {err or proc.returncode}")
        pcm = out_path.read_bytes()
        if not pcm:
            raise XfyunAsrError("转码后音频为空")
        return pcm
    finally:
        inp_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)
