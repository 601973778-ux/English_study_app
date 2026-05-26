from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Spoken_model.rag.chunk_models import tokenize, write_jsonl
from Spoken_model.rag.ingest.parse_book1_md import parse_book1_md
from Spoken_model.rag.ingest.parse_deepseek_scenario_md import parse_deepseek_scenario_md
from Spoken_model.rag.retrieval.tfidf_index import TfidfIndex, build_tfidf_index, cosine_sparse

WORKSPACE = Path(__file__).resolve().parents[2]
RAG_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = RAG_ROOT / "config" / "corpus_manifest.json"
DEFAULT_MD = WORKSPACE / "Spoken_model" / "Communication_Data" / "Book1_p1_p370.md"
CORPUS_DIR = RAG_ROOT / "corpus"
INDEX_DIR = RAG_ROOT / "index"

PARSERS = {
    "book1_md": parse_book1_md,
    "deepseek_scenario_md": parse_deepseek_scenario_md,
}


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_source(source: dict[str, Any], *, corpus_id: str) -> list:
    parser_name = str(source.get("parser") or "")
    parser = PARSERS.get(parser_name)
    if parser is None:
        raise ValueError(f"unknown parser: {parser_name}")
    md_path = WORKSPACE / str(source["path"])
    kwargs: dict[str, Any] = {
        "corpus_id": corpus_id,
        "source_id": str(source.get("source_id") or md_path.stem),
    }
    if parser_name == "deepseek_scenario_md":
        tags = source.get("default_scenario_tags")
        if tags:
            kwargs["default_scenario_tags"] = list(tags)
    return parser(md_path, **kwargs)


def build_knowledge_base(
    md_path: Path | None = None,
    *,
    manifest_path: Path = MANIFEST_PATH,
    corpus_version: str | None = None,
) -> dict[str, Any]:
    if md_path is not None:
        chunks = parse_book1_md(md_path)
        corpus_id = corpus_version or "spoken_book1_v1"
        source_files = [str(md_path.as_posix())]
    else:
        manifest = load_manifest(manifest_path)
        corpus_id = corpus_version or str(manifest.get("corpus_id") or "spoken_corpus_v1")
        chunks = []
        source_files = []
        for source in manifest.get("sources") or []:
            part = parse_source(source, corpus_id=corpus_id)
            chunks.extend(part)
            source_files.append(str((WORKSPACE / source["path"]).as_posix()))

    chunks_path = CORPUS_DIR / "chunks.jsonl"
    write_jsonl(chunks_path, (c.to_dict() for c in chunks))

    chunk_dicts = load_chunks_jsonl(chunks_path)
    tfidf = build_tfidf_index(chunk_dicts, corpus_version=corpus_id)
    tfidf.save(INDEX_DIR)

    manifest_out = {
        **tfidf.manifest,
        "source_files": source_files,
        "chunks_file": str(chunks_path.as_posix()),
        "index_file": str((INDEX_DIR / "tfidf_index.json").as_posix()),
    }
    (INDEX_DIR / "manifest.json").write_text(
        json.dumps(manifest_out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for c in chunks:
        by_type[c.chunk_type] = by_type.get(c.chunk_type, 0) + 1
        by_source[c.source_id] = by_source.get(c.source_id, 0) + 1

    return {
        "chunk_count": len(chunks),
        "by_type": by_type,
        "by_source": by_source,
        "topics": len({c.topic_id for c in chunks}),
        "manifest": manifest_out,
    }


def search(
    query: str,
    *,
    top_k: int = 5,
    scenario_tags: list[str] | None = None,
    chunk_types: list[str] | None = None,
    topic_id: int | None = None,
    source_id: str | None = None,
) -> list[dict[str, Any]]:
    chunks_path = CORPUS_DIR / "chunks.jsonl"
    index = TfidfIndex.load(INDEX_DIR)
    chunk_map = {row["chunk_id"]: row for row in load_chunks_jsonl(chunks_path)}

    q_vec = _query_vector(query, index.idf)
    scored: list[tuple[float, str]] = []
    for cid, vec in zip(index.chunk_ids, index.vectors):
        meta = chunk_map.get(cid)
        if meta is None:
            continue
        if topic_id is not None and int(meta.get("topic_id", -1)) != topic_id:
            continue
        if source_id is not None and str(meta.get("source_id") or "") != source_id:
            continue
        if chunk_types and meta.get("chunk_type") not in chunk_types:
            continue
        if scenario_tags:
            tags = set(meta.get("scenario_tags") or [])
            if not tags.intersection(scenario_tags):
                continue
        score = cosine_sparse(q_vec, vec)
        if score > 0:
            scored.append((score, cid))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for score, cid in scored[:top_k]:
        row = dict(chunk_map[cid])
        row["score"] = round(score, 4)
        out.append(row)
    return out


def _query_vector(query: str, idf: dict[str, float]) -> dict[str, float]:
    from collections import Counter
    import math

    tokens = tokenize(query)
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    vec = {term: (count / total) * idf.get(term, 0.0) for term, count in counts.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def main() -> None:
    import argparse
    import sys

    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))

    parser = argparse.ArgumentParser(description="Build spoken dialogue RAG knowledge base")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Optional single markdown (Book1 only); default builds all sources in manifest",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="",
        help="Optional test query after build",
    )
    args = parser.parse_args()

    stats = build_knowledge_base(args.input)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if args.query.strip():
        hits = search(args.query, top_k=5)
        print("\nTest search:")
        print(json.dumps(hits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
