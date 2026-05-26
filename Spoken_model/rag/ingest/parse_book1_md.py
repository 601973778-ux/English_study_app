from __future__ import annotations

import html
import json
import re
from pathlib import Path

from Spoken_model.rag.chunk_models import (
    Chunk,
    build_embedding_text,
    has_cjk,
    is_primarily_english,
    normalize_ws,
    strip_list_marker,
)

_TOPIC_RE = re.compile(r"^# (\d+)\.\s*(.+)$")
_DIALOGUE_RE = re.compile(r"^# Dialogue\s+(\d+)", re.I)
_SECTION_USEFUL_RE = re.compile(r"^#?\s*Useful Expressions\s*$", re.I)
_SECTION_WORDS_RE = re.compile(r"^#?\s*Words Storm\s*$", re.I)
_SPEAKER_LINE_RE = re.compile(r"^(.+?):\s*(.+)$")
_SKIP_PREFIXES = ("# 练习", "# 答案", "# I.", "# II.", "# III.", "# Responding")


def _load_scenario_tags(config_path: Path) -> dict[int, list[str]]:
    if not config_path.is_file():
        return {}
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return {int(k): list(v) for k, v in raw.items()}


def _table_cells(line: str) -> list[str]:
    if "<table" not in line and "</td>" not in line:
        return []
    unescaped = html.unescape(line)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", unescaped, flags=re.I | re.S)
    out: list[str] = []
    for cell in cells:
        text = re.sub(r"<[^>]+>", " ", cell)
        text = normalize_ws(text)
        if text and has_cjk(text):
            out.append(text)
    return out


def _flush_useful_pairs(
    en_lines: list[str],
    zh_lines: list[str],
    *,
    ctx: dict,
    chunks: list[Chunk],
    line_no: int,
) -> None:
    if not en_lines:
        return
    for i, en in enumerate(en_lines):
        zh = zh_lines[i] if i < len(zh_lines) else ""
        _append_chunk(
            chunks,
            chunk_type="useful_expression",
            text_en=en,
            text_zh=zh,
            ctx=ctx,
            seq=len(chunks),
            line_no=line_no,
        )
    en_lines.clear()
    zh_lines.clear()


def _append_chunk(
    chunks: list[Chunk],
    *,
    chunk_type: str,
    text_en: str,
    text_zh: str,
    ctx: dict,
    seq: int,
    line_no: int,
    dialogue_id: str = "",
    turn_index: int = 0,
    speaker: str = "",
) -> None:
    text_en = normalize_ws(text_en)
    text_zh = normalize_ws(text_zh)
    if not text_en and not text_zh:
        return
    topic_id = ctx["topic_id"]
    chunk_id = f"book1:t{topic_id:03d}:{chunk_type}:{seq:04d}"
    tags = list(ctx.get("scenario_tags", []))
    chunk = Chunk(
        chunk_id=chunk_id,
        chunk_type=chunk_type,
        corpus_id=ctx["corpus_id"],
        source_id=ctx["source_id"],
        topic_id=topic_id,
        topic_title_en=ctx["topic_title_en"],
        topic_title_zh=ctx["topic_title_zh"],
        text_en=text_en,
        text_zh=text_zh,
        text_for_embedding=build_embedding_text(
            chunk_type=chunk_type,
            topic_title_en=ctx["topic_title_en"],
            topic_title_zh=ctx["topic_title_zh"],
            text_en=text_en,
            text_zh=text_zh,
            scenario_tags=tags,
        ),
        scenario_tags=tags,
        dialogue_id=dialogue_id,
        turn_index=turn_index,
        speaker=speaker,
        source_file=ctx["source_file"],
        source_line=line_no,
    )
    chunks.append(chunk)


def parse_book1_md(
    md_path: Path,
    *,
    corpus_id: str = "spoken_book1_v1",
    source_id: str = "book1",
    scenario_tags_path: Path | None = None,
) -> list[Chunk]:
    scenario_map = _load_scenario_tags(
        scenario_tags_path
        or Path(__file__).resolve().parent.parent / "config" / "topic_scenario_tags.json"
    )
    lines = md_path.read_text(encoding="utf-8").splitlines()
    chunks: list[Chunk] = []

    topic_id = 0
    topic_title_en = ""
    topic_title_zh = ""
    section = ""
    dialogue_id = ""
    dialogue_lang = "en"
    dialogue_turn = 0

    useful_en: list[str] = []
    useful_zh: list[str] = []
    pending_zh_title = False

    ctx: dict = {
        "corpus_id": corpus_id,
        "source_id": source_id,
        "source_file": str(md_path.as_posix()),
        "topic_id": 0,
        "topic_title_en": "",
        "topic_title_zh": "",
        "scenario_tags": [],
    }

    def reset_topic(new_id: int, title_en: str) -> None:
        nonlocal topic_id, topic_title_en, topic_title_zh
        nonlocal section, dialogue_id, dialogue_lang, dialogue_turn, pending_zh_title
        _flush_useful_pairs(useful_en, useful_zh, ctx=ctx, chunks=chunks, line_no=0)
        topic_id = new_id
        topic_title_en = title_en.strip()
        topic_title_zh = ""
        section = ""
        dialogue_id = ""
        dialogue_lang = "en"
        dialogue_turn = 0
        pending_zh_title = True
        ctx.update(
            {
                "topic_id": topic_id,
                "topic_title_en": topic_title_en,
                "topic_title_zh": "",
                "scenario_tags": scenario_map.get(topic_id, []),
            }
        )

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!["):
            continue
        if any(line.startswith(p) for p in _SKIP_PREFIXES):
            section = "skip"
            continue

        m_topic = _TOPIC_RE.match(line)
        if m_topic:
            reset_topic(int(m_topic.group(1)), m_topic.group(2))
            continue

        if topic_id <= 0:
            continue

        if pending_zh_title and line.startswith("# ") and has_cjk(line):
            topic_title_zh = line.lstrip("# ").strip()
            ctx["topic_title_zh"] = topic_title_zh
            pending_zh_title = False
            continue
        pending_zh_title = False

        if _SECTION_WORDS_RE.match(line):
            _flush_useful_pairs(useful_en, useful_zh, ctx=ctx, chunks=chunks, line_no=line_no)
            section = "words"
            continue
        if _SECTION_USEFUL_RE.match(line):
            _flush_useful_pairs(useful_en, useful_zh, ctx=ctx, chunks=chunks, line_no=line_no)
            section = "useful"
            continue
        m_dialogue = _DIALOGUE_RE.match(line)
        if m_dialogue:
            _flush_useful_pairs(useful_en, useful_zh, ctx=ctx, chunks=chunks, line_no=line_no)
            section = "dialogue"
            dialogue_id = f"dialogue_{m_dialogue.group(1)}"
            dialogue_lang = "en"
            dialogue_turn = 0
            continue

        if section == "skip":
            continue

        if section == "words":
            for cell in _table_cells(line):
                if re.search(r"/[^/]+/", cell):
                    text_en = re.split(r"\s+/[^/]+/\s*", cell)[0].strip()
                    text_zh = cell.split()[-1] if has_cjk(cell) else ""
                else:
                    text_en, _, text_zh = cell.partition(" ")
                _append_chunk(
                    chunks,
                    chunk_type="vocabulary",
                    text_en=text_en,
                    text_zh=text_zh,
                    ctx=ctx,
                    seq=len(chunks),
                    line_no=line_no,
                )
            if "<table" not in line and not line.startswith("<"):
                plain = normalize_ws(line)
                if plain and (has_cjk(plain) or is_primarily_english(plain)):
                    _append_chunk(
                        chunks,
                        chunk_type="vocabulary",
                        text_en=plain if is_primarily_english(plain) else "",
                        text_zh=plain if has_cjk(plain) else "",
                        ctx=ctx,
                        seq=len(chunks),
                        line_no=line_no,
                    )
            continue

        if section == "useful":
            clean = strip_list_marker(line)
            if is_primarily_english(clean):
                useful_en.append(clean)
            elif has_cjk(clean):
                useful_zh.append(clean)
            continue

        if section == "dialogue":
            m_sp = _SPEAKER_LINE_RE.match(line)
            if not m_sp:
                continue
            speaker = normalize_ws(m_sp.group(1))
            utterance = normalize_ws(m_sp.group(2))
            if dialogue_lang == "en":
                if is_primarily_english(utterance):
                    dialogue_turn += 1
                    _append_chunk(
                        chunks,
                        chunk_type="dialogue_turn",
                        text_en=utterance,
                        text_zh="",
                        ctx=ctx,
                        seq=len(chunks),
                        line_no=line_no,
                        dialogue_id=dialogue_id,
                        turn_index=dialogue_turn,
                        speaker=speaker,
                    )
                elif has_cjk(utterance):
                    dialogue_lang = "zh"
            if dialogue_lang == "zh" and has_cjk(utterance):
                for chunk in reversed(chunks):
                    if (
                        chunk.chunk_type == "dialogue_turn"
                        and chunk.topic_id == topic_id
                        and chunk.dialogue_id == dialogue_id
                        and not chunk.text_zh
                    ):
                        chunk.text_zh = utterance
                        chunk.text_for_embedding = build_embedding_text(
                            chunk_type=chunk.chunk_type,
                            topic_title_en=chunk.topic_title_en,
                            topic_title_zh=chunk.topic_title_zh,
                            text_en=chunk.text_en,
                            text_zh=chunk.text_zh,
                            scenario_tags=chunk.scenario_tags,
                        )
                        break
            continue

    _flush_useful_pairs(useful_en, useful_zh, ctx=ctx, chunks=chunks, line_no=0)
    return chunks
