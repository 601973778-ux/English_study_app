"""进程内词库缓存：按词书路径加载 load_words，切换词书时失效。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

_entries: list[Any] | None = None
_entries_resolved: str | None = None


def get_entries(resolve_path: Callable[[], Path]) -> list[Any]:
    global _entries, _entries_resolved
    from Vocabulary_model.study_words_cli import load_words

    path = resolve_path().resolve()
    key = str(path)
    if _entries is None or _entries_resolved != key:
        _entries = load_words(path)
        _entries_resolved = key
    return _entries


def invalidate_entries() -> None:
    global _entries, _entries_resolved
    _entries = None
    _entries_resolved = None
