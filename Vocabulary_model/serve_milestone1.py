#!/usr/bin/env python3
"""
在 English_study_app 根目录启动服务：
- 静态文件：/milestone1/index.html
- 学习接口：/api/*
用法: 在本目录执行  python serve_milestone1.py
然后浏览器打开输出的地址，进入 /milestone1/index.html
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

try:
    # 当从仓库根目录以模块方式运行时可用
    from Vocabulary_model.study_words_cli import DEFAULT_SOURCE, StudySession, load_words
    from Vocabulary_model.Vocal_model import XfyunTtsError, synthesize_english_word
except ModuleNotFoundError:  # pragma: no cover
    # 当直接执行 d:/.../milestone1/serve_milestone1.py 时可用
    from study_words_cli import DEFAULT_SOURCE, StudySession, load_words
    from Vocal_model import XfyunTtsError, synthesize_english_word

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PORT = 8766


_ENTRIES: list[Any] | None = None
_SESSION: StudySession | None = None


def _ensure_entries(source: Path = DEFAULT_SOURCE):
    global _ENTRIES
    if _ENTRIES is None:
        _ENTRIES = load_words(source)
    return _ENTRIES


def _pick_port() -> int:
    """
    Choose a listening port.
    - If env PORT is set, try it first.
    - Otherwise start from DEFAULT_PORT, and if occupied, try the next ports.
    """
    env_port = (os.environ.get("PORT") or "").strip()
    start = DEFAULT_PORT
    if env_port:
        try:
            start = int(env_port)
        except ValueError:
            start = DEFAULT_PORT

    for port in range(start, start + 50):
        try:
            with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as _:
                return port
        except OSError:
            continue
    raise OSError("no available port found")


class Milestone1Handler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, obj: object, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _api_state(self) -> dict:
        entries = _ensure_entries()
        if _SESSION is None:
            return {
                "phase": "idle",
                "word": "点击“开始学习”",
                "meaning": "中文释义会在你作答后显示。",
                "meta": f"词库加载成功，共 {len(entries)} 条",
                "ui": {
                    "startEnabled": True,
                    "knownEnabled": False,
                    "unknownEnabled": False,
                    "showMistake": False,
                    "showNext": False,
                },
            }
        return _SESSION.state()

    def do_GET(self) -> None:
        if self.path.startswith("/api/state"):
            try:
                self._send_json(self._api_state())
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if self.path.startswith("/api/tts"):
            try:
                u = urlparse(self.path)
                qs = parse_qs(u.query or "")
                text = (qs.get("text", [""])[0] or "").strip()
                audio, content_type = synthesize_english_word(text)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(audio)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(audio)
            except XfyunTtsError as e:
                self._send_json({"error": str(e)}, status=400)
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        global _SESSION
        if not self.path.startswith("/api/"):
            self.send_error(404, "Not Found")
            return

        try:
            payload = self._read_json()

            if self.path == "/api/start":
                entries = _ensure_entries()
                count = payload.get("count", 50)
                try:
                    count_int = int(count)
                except (TypeError, ValueError):
                    count_int = 50
                _SESSION = StudySession(entries, count=count_int)
                self._send_json(_SESSION.start())
                return

            if _SESSION is None:
                self._send_json({"error": "session not started"}, status=400)
                return

            if self.path == "/api/known":
                self._send_json(_SESSION.answer_known())
                return
            if self.path == "/api/unknown":
                self._send_json(_SESSION.answer_unknown())
                return
            if self.path == "/api/mistake":
                self._send_json(_SESSION.mistake_after_known())
                return
            if self.path == "/api/next":
                self._send_json(_SESSION.next_after_meaning())
                return

            self._send_json({"error": "unknown api"}, status=404)
        except Exception as e:  # noqa: BLE001
            self._send_json({"error": str(e)}, status=500)


def main() -> None:
    os.chdir(ROOT)
    handler = Milestone1Handler
    port = _pick_port()
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/Vocabulary_model/index.html"
        print(f"Serving {ROOT}")
        print(f"Open: {url}")
        print("Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except OSError:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
