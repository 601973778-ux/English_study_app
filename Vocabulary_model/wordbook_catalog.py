"""
词书目录：当前词库路径与可扩展词书元数据（CET4 / GRE / TOEFL / 专四 / 专八 等预留）。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

_VM = Path(__file__).resolve().parent
_WORKSPACE = _VM.parent
_WORD_DATA = _VM / "Word_data"


@dataclasses.dataclass(frozen=True, slots=True)
class WordbookSpec:
    id: str
    label: str
    path: Path

    @property
    def available(self) -> bool:
        return self.path.is_file()


# 新增词书：在 Word_data 放入对应 JSON 后，将 available 由路径自动判定。
WORDBOOKS: tuple[WordbookSpec, ...] = (
    WordbookSpec(
        id="cet6",
        label="大学英语六级 (CET-6)",
        path=_WORD_DATA / "CET6_edited.json",
    ),
    WordbookSpec(
        id="cet4",
        label="大学英语四级 (CET-4)",
        path=_WORD_DATA / "CET4_edited.json",
    ),
    WordbookSpec(
        id="gre",
        label="GRE",
        path=_WORD_DATA / "GRE_edited.json",
    ),
    WordbookSpec(
        id="toefl",
        label="托福 TOEFL",
        path=_WORD_DATA / "TOEFL_edited.json",
    ),
    WordbookSpec(
        id="tem4",
        label="英语专业四级 (TEM-4)",
        path=_WORD_DATA / "TEM4_edited.json",
    ),
    WordbookSpec(
        id="tem8",
        label="英语专业八级 (TEM-8)",
        path=_WORD_DATA / "TEM8_edited.json",
    ),
)

_BY_ID: dict[str, WordbookSpec] = {s.id: s for s in WORDBOOKS}
DEFAULT_WORDBOOK_ID = "cet6"


def list_wordbooks_public() -> list[dict[str, str | bool]]:
    """供 GET /api/wordbooks 使用。"""
    return [{"id": s.id, "label": s.label, "available": s.available} for s in WORDBOOKS]


def get_spec(wordbook_id: str) -> WordbookSpec | None:
    return _BY_ID.get(str(wordbook_id or "").strip().lower())


def is_wordbook_available(wordbook_id: str) -> bool:
    s = get_spec(wordbook_id)
    return bool(s and s.available)


def normalize_wordbook_id(wordbook_id: str) -> str:
    wid = str(wordbook_id or "").strip().lower()
    if wid not in _BY_ID:
        return DEFAULT_WORDBOOK_ID
    if not is_wordbook_available(wid):
        return DEFAULT_WORDBOOK_ID
    return wid


def resolve_wordbook_path(wordbook_id: str) -> Path:
    """解析为可读词库文件路径；不可用时回退到 CET6。"""
    wid = normalize_wordbook_id(wordbook_id)
    spec = _BY_ID[wid]
    return spec.path


def wordbook_label(wordbook_id: str) -> str:
    wid = normalize_wordbook_id(wordbook_id)
    return _BY_ID[wid].label


def similar_index_path(wordbook_id: str) -> Path:
    """形近词邻接表路径，与词书 JSON 同目录，如 CET6_similar_shape_words.json。"""
    wid = normalize_wordbook_id(wordbook_id)
    spec = _BY_ID[wid]
    stem = spec.path.stem
    if stem.endswith("_edited"):
        base = stem[: -len("_edited")]
    else:
        base = stem
    return spec.path.parent / f"{base}_similar_shape_words.json"
