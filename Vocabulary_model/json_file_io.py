"""JSON 文件持久化：进程内加锁，Windows 下可重试的原子写入。"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _path_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def save_json_atomic(
    path: Path | str,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
    if not text.endswith("\n"):
        text += "\n"
    with _path_lock(path):
        _write_text_atomic(path, text)


def _write_text_atomic(path: Path, text: str) -> None:
    pid = os.getpid()
    tid = threading.get_ident()
    tmp = path.parent / f"{path.name}.{pid}.{tid}.tmp"
    max_attempts = 8
    delay = 0.02
    last_err: BaseException | None = None

    for attempt in range(max_attempts):
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            return
        except (PermissionError, OSError) as err:
            last_err = err
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt + 1 >= max_attempts:
                break
            time.sleep(delay)
            delay = min(delay * 2, 0.5)

    for attempt in range(max_attempts):
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return
        except (PermissionError, OSError) as err:
            last_err = err
            if attempt + 1 >= max_attempts:
                break
            time.sleep(delay)
            delay = min(delay * 2, 0.5)

    raise OSError(
        f"无法写入 {path}（可能被其他程序占用，请关闭多余的 server 或编辑器后重试）"
    ) from last_err
