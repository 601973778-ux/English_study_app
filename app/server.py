#!/usr/bin/env python3
"""
接入服务器（与 v0.5 思路一致）
============================

- 静态根目录：仓库根 ``English_study_app``，访问 ``/app/index.html``。
- ``/api/*`` 与 ``Vocabulary_model/serve_milestone1.py`` 语义一致，直接复用同目录下模块。

启动（在仓库根目录）::

    python app/server.py

浏览器打开 ``http://127.0.0.1:<端口>/app/index.html``。
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import socketserver
import sys
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from Vocabulary_model.similar_neighbors_service import (  # noqa: E402
    invalidate_similar_cache,
    set_entry_cache,
    set_similar_wordbook,
    similar_words_payload,
)
from Vocabulary_model.study_words_cli import StudySession  # noqa: E402
from Vocabulary_model.Vocal_model import XfyunTtsError, synthesize_english_word  # noqa: E402
from Vocabulary_model.user_settings import load_user_settings, save_user_settings  # noqa: E402
from Vocabulary_model.xfyun_credentials_store import (  # noqa: E402
    get_tts_config_public,
    save_tts_config,
)
from Vocabulary_model.wordbook_catalog import (  # noqa: E402
    list_wordbooks_public,
    resolve_wordbook_path,
    wordbook_label,
)
from Vocabulary_model.wordbook_entries_cache import get_entries, invalidate_entries  # noqa: E402
from Vocabulary_model.daily_progress_store import DailyProgressStore  # noqa: E402
from Vocabulary_model.daily_session_service import (  # noqa: E402
    _merge_progress,
    idle_progress_state,
    on_session_action,
    start_or_resume,
)

DEFAULT_PORT = 8766


def _load_review_store_class():
    module_file = WORKSPACE / "Vocabulary_model" / "review&reciting_data.py"
    spec = importlib.util.spec_from_file_location("review_reciting_data_app", module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载复习数据库模块: {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cls = getattr(module, "ReviewRecitingDataStore", None)
    if cls is None:
        raise RuntimeError("review&reciting_data.py 中缺少 ReviewRecitingDataStore")
    return cls


_SESSION: StudySession | None = None
_REVIEW_STORE = _load_review_store_class()()
_DAILY_STORE = DailyProgressStore()


def _resolve_wordbook_path():
    s = load_user_settings()
    return resolve_wordbook_path(str(s.get("wordbook_id", "cet6")))


def _ensure_entries():
    s = load_user_settings()
    wid = str(s.get("wordbook_id", "cet6"))
    entries = get_entries(_resolve_wordbook_path)
    set_entry_cache(entries)
    set_similar_wordbook(wid)
    return entries


def _pick_port() -> int:
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


class AppHandler(http.server.SimpleHTTPRequestHandler):
    def _parsed_request(self) -> tuple[str, str]:
        raw = (self.path or "").strip()
        if not raw:
            return "/", ""
        u = urlparse(raw)
        path = u.path or "/"
        if not path.startswith("/"):
            path = "/" + path.lstrip("/")
        while "//" in path:
            path = path.replace("//", "/")
        return path, u.query or ""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

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

    def _wordbook_context(self) -> tuple[str, str, list]:
        entries = _ensure_entries()
        s = load_user_settings()
        wid = str(s.get("wordbook_id", "cet6"))
        return wid, wordbook_label(wid), entries

    def _api_state(self) -> dict:
        wid, label, entries = self._wordbook_context()
        if _SESSION is None:
            return idle_progress_state(len(entries), wid, label)
        return _merge_progress(_SESSION.state(), _DAILY_STORE.progress_payload(wid))

    def _persist_session_words(self, *, graduated_word: str | None = None) -> None:
        if _SESSION is None:
            return
        wid = str(load_user_settings().get("wordbook_id", "cet6"))
        clean = str(graduated_word or "").strip()
        if clean:
            _REVIEW_STORE.mark_learned_words([clean], wordbook_id=wid)
            _REVIEW_STORE.mark_proficient(clean, wordbook_id=wid)
        for w in _SESSION.fuzzy_words:
            _REVIEW_STORE.mark_fuzzy(w, wordbook_id=wid)
        for w in _SESSION.unknown_words:
            _REVIEW_STORE.mark_unfamiliar(w, wordbook_id=wid)

    def do_GET(self) -> None:
        req_path, req_query = self._parsed_request()
        if req_path.startswith("/api/state"):
            try:
                self._send_json(self._api_state())
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if req_path.startswith("/api/settings"):
            try:
                s = load_user_settings()
                out = dict(s)
                out["wordbook_label"] = wordbook_label(str(s.get("wordbook_id", "cet6")))
                self._send_json(out)
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if req_path.startswith("/api/wordbooks"):
            try:
                self._send_json({"items": list_wordbooks_public()})
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if req_path.startswith("/api/similar-for"):
            try:
                qs = parse_qs(req_query)
                word = (qs.get("word", [""])[0] or "").strip()
                if not word:
                    self._send_json({"error": "missing word"}, status=400)
                    return
                _ensure_entries()
                s = load_user_settings()
                self._send_json(
                    similar_words_payload(word, str(s.get("wordbook_id", "cet6")))
                )
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if req_path.startswith("/api/tts-config"):
            try:
                self._send_json(get_tts_config_public())
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        if req_path.startswith("/api/tts"):
            try:
                qs = parse_qs(req_query)
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
        if req_path.startswith("/api/learning-stats"):
            try:
                self._persist_session_words()
                qs = parse_qs(req_query)
                limit_raw = (qs.get("limit", ["200"])[0] or "200").strip()
                try:
                    limit = int(limit_raw)
                except ValueError:
                    limit = 200
                wid = str(load_user_settings().get("wordbook_id", "cet6"))
                self._send_json(_REVIEW_STORE.get_learning_stats(limit=limit, wordbook_id=wid))
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, status=500)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        global _SESSION
        req_path, _req_query = self._parsed_request()
        if not req_path.startswith("/api/"):
            self.send_error(404, "Not Found")
            return
        try:
            payload = self._read_json()
            if req_path == "/api/start":
                wid, label, entries = self._wordbook_context()
                user_settings = load_user_settings()
                count = payload.get("count", user_settings.get("daily_words", 50))
                try:
                    count_int = int(count)
                except (TypeError, ValueError):
                    count_int = 50
                _SESSION, state = start_or_resume(
                    entries,
                    wordbook_id=wid,
                    wordbook_label=label,
                    review_store=_REVIEW_STORE,
                    daily_words=count_int,
                    review_ratio=str(user_settings.get("review_ratio", "1:1")),
                )
                self._send_json(state)
                return
            if req_path == "/api/session/save":
                if _SESSION is None:
                    self._send_json({"ok": True})
                    return
                wid, _, _ = self._wordbook_context()
                on_session_action(_DAILY_STORE, wid, _SESSION)
                self._send_json({"ok": True})
                return
            if req_path == "/api/tts-config":
                try:
                    self._send_json(save_tts_config(payload))
                except ValueError as e:
                    self._send_json({"error": str(e)}, status=400)
                return
            if req_path == "/api/settings":
                prev = load_user_settings()
                prev_wb = str(prev.get("wordbook_id", "cet6"))
                settings = save_user_settings(payload)
                if str(settings.get("wordbook_id", "cet6")) != prev_wb:
                    invalidate_entries()
                    invalidate_similar_cache(prev_wb)
                    invalidate_similar_cache(str(settings.get("wordbook_id", "cet6")))
                    _SESSION = None
                self._send_json(
                    {
                        **settings,
                        "wordbook_label": wordbook_label(str(settings.get("wordbook_id", "cet6"))),
                    }
                )
                return
            if _SESSION is None:
                self._send_json({"error": "session not started"}, status=400)
                return
            wid, _, _ = self._wordbook_context()
            if req_path == "/api/known":
                _SESSION.answer_known()
                self._persist_session_words()
                self._send_json(on_session_action(_DAILY_STORE, wid, _SESSION))
                return
            if req_path == "/api/unknown":
                _SESSION.answer_unknown()
                self._persist_session_words()
                self._send_json(on_session_action(_DAILY_STORE, wid, _SESSION))
                return
            if req_path == "/api/mistake":
                _SESSION.mistake_after_known()
                self._persist_session_words()
                self._send_json(on_session_action(_DAILY_STORE, wid, _SESSION))
                return
            if req_path == "/api/next":
                done = _SESSION.peek_word_completed_on_next()
                _SESSION.next_after_meaning()
                self._persist_session_words(graduated_word=done)
                self._send_json(
                    on_session_action(
                        _DAILY_STORE, wid, _SESSION, just_completed_word=done
                    )
                )
                return
            self._send_json({"error": "unknown api"}, status=404)
        except Exception as e:  # noqa: BLE001
            self._send_json({"error": str(e)}, status=500)


def main() -> None:
    os.chdir(WORKSPACE)
    port = _pick_port()
    with socketserver.TCPServer(("", port), AppHandler) as httpd:
        url = f"http://127.0.0.1:{port}/app/index.html"
        print(f"工作区根目录: {WORKSPACE}")
        print(f"服务地址    : {url}")
        print("Ctrl+C 停止")
        try:
            webbrowser.open(url)
        except OSError:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
