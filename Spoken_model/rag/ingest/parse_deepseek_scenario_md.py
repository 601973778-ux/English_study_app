from __future__ import annotations

import json
import re
from pathlib import Path

from Spoken_model.rag.chunk_models import (
    Chunk,
    build_embedding_text,
    has_cjk,
    is_primarily_english,
    normalize_ws,
)

_SCENARIO_RE = re.compile(r"^##\s*场景([^\s：:]+)[：:]\s*(.+)$")
_SUMMARY_SECTION_RE = re.compile(r"^##\s*高频实用句型总结\s*$")
_SUBSECTION_RE = re.compile(r"^###\s+(.+)$")
_SKIP_LINE_PREFIXES = (">", "**适用级别**", "**场景覆盖**")

# topic_id 9001+ reserved for deepseek restaurant scenarios (avoid Book1 1–100)
TOPIC_ID_BASE = 9000
SUMMARY_TOPIC_ID = 9099


def _load_scenario_tags(config_path: Path) -> dict[int, list[str]]:
    if not config_path.is_file():
        return {}
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return {int(k): list(v) for k, v in raw.items()}


def _parse_table_cells(line: str) -> list[str]:
    if not line.startswith("|"):
        return []
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_table_separator(cells: list[str]) -> bool:
    if not cells:
        return True
    return all(re.fullmatch(r"[-:\s]+", c or "-") for c in cells)


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
    topic_id = int(ctx["topic_id"])
    source_id = str(ctx["source_id"])
    chunk_id = f"{source_id}:t{topic_id:04d}:{chunk_type}:{seq:04d}"
    tags = list(ctx.get("scenario_tags", []))
    chunk = Chunk(
        chunk_id=chunk_id,
        chunk_type=chunk_type,
        corpus_id=ctx["corpus_id"],
        source_id=source_id,
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


def parse_deepseek_scenario_md(
    md_path: Path,
    *,
    corpus_id: str = "spoken_corpus_v1",
    source_id: str = "deepseek_restaurant",
    scenario_tags_path: Path | None = None,
    default_scenario_tags: list[str] | None = None,
) -> list[Chunk]:
    """Parse DeepSeek-generated restaurant scenario markdown (table dialogue + phrase lists)."""

    tag_map = _load_scenario_tags(
        scenario_tags_path
        or Path(__file__).resolve().parent.parent / "config" / "topic_scenario_tags.json"
    )
    fallback_tags = default_scenario_tags or ["restaurant", "ordering", "dining", "eating_out"]
    lines = md_path.read_text(encoding="utf-8").splitlines()
    chunks: list[Chunk] = []

    topic_id = 0
    topic_title_en = ""
    topic_title_zh = ""
    scenario_index = 0
    subsection = ""
    dialogue_id = ""
    dialogue_turn = 0
    table_mode: str | None = None  # dialogue | phrase

    ctx: dict = {
        "corpus_id": corpus_id,
        "source_id": source_id,
        "source_file": str(md_path.as_posix()),
        "topic_id": 0,
        "topic_title_en": "",
        "topic_title_zh": "",
        "scenario_tags": fallback_tags,
    }

    def reset_scenario(title_zh: str, *, tid: int, index: int) -> None:
        nonlocal topic_id, topic_title_en, topic_title_zh
        nonlocal subsection, dialogue_id, dialogue_turn, table_mode
        topic_id = tid
        topic_title_en = f"Scenario {index}"
        topic_title_zh = title_zh.strip()
        subsection = ""
        dialogue_id = ""
        dialogue_turn = 0
        table_mode = None
        ctx.update(
            {
                "topic_id": topic_id,
                "topic_title_en": topic_title_en,
                "topic_title_zh": topic_title_zh,
                "scenario_tags": tag_map.get(topic_id, fallback_tags),
            }
        )

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith(_SKIP_LINE_PREFIXES):
            continue

        if _SUMMARY_SECTION_RE.match(line):
            reset_scenario("高频实用句型总结", tid=SUMMARY_TOPIC_ID, index=0)
            continue

        m_scene = _SCENARIO_RE.match(line)
        if m_scene:
            scenario_index += 1
            reset_scenario(m_scene.group(2), tid=TOPIC_ID_BASE + scenario_index, index=scenario_index)
            continue

        if topic_id <= 0:
            continue

        m_sub = _SUBSECTION_RE.match(line)
        if m_sub:
            subsection = normalize_ws(m_sub.group(1))
            slug = re.sub(r"\W+", "_", subsection.lower())[:40] or "section"
            dialogue_id = f"{topic_id}_{slug}"
            dialogue_turn = 0
            table_mode = None
            continue

        if line.startswith("**情景**") or line.startswith("**角色**"):
            continue

        if line.startswith("|"):
            cells = _parse_table_cells(line)
            if _is_table_separator(cells):
                continue
            header_joined = " ".join(cells)
            if "角色" in header_joined and ("英语" in header_joined or "台词" in header_joined):
                table_mode = "dialogue"
                continue
            if ("英语" in cells[0] if cells else False) or header_joined in ("英语 中文", "English 中文"):
                table_mode = "phrase"
                continue

            if table_mode == "dialogue" and len(cells) >= 3:
                role, text_en, text_zh = cells[0], cells[1], cells[2]
                if role.lower() in ("角色", "role"):
                    continue
                dialogue_turn += 1
                _append_chunk(
                    chunks,
                    chunk_type="dialogue_turn",
                    text_en=text_en,
                    text_zh=text_zh,
                    ctx=ctx,
                    seq=len(chunks),
                    line_no=line_no,
                    dialogue_id=dialogue_id or f"scenario_{topic_id}",
                    turn_index=dialogue_turn,
                    speaker=role,
                )
                continue

            if table_mode == "phrase" and len(cells) >= 2:
                text_en, text_zh = cells[0], cells[1]
                if text_en in ("英语", "English") or text_zh in ("中文", "Chinese"):
                    continue
                _append_chunk(
                    chunks,
                    chunk_type="useful_expression",
                    text_en=text_en,
                    text_zh=text_zh,
                    ctx=ctx,
                    seq=len(chunks),
                    line_no=line_no,
                )
                continue

            # Fallback: 3-column without explicit header mode
            if len(cells) >= 3 and not has_cjk(cells[0]):
                dialogue_turn += 1
                _append_chunk(
                    chunks,
                    chunk_type="dialogue_turn",
                    text_en=cells[1],
                    text_zh=cells[2],
                    ctx=ctx,
                    seq=len(chunks),
                    line_no=line_no,
                    dialogue_id=dialogue_id or f"scenario_{topic_id}",
                    turn_index=dialogue_turn,
                    speaker=cells[0],
                )
            elif len(cells) >= 2 and is_primarily_english(cells[0]):
                _append_chunk(
                    chunks,
                    chunk_type="useful_expression",
                    text_en=cells[0],
                    text_zh=cells[1],
                    ctx=ctx,
                    seq=len(chunks),
                    line_no=line_no,
                )
            continue

    return chunks
