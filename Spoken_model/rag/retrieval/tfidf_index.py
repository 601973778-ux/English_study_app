from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Spoken_model.rag.chunk_models import tokenize


@dataclass
class TfidfIndex:
    chunk_ids: list[str]
    idf: dict[str, float]
    vectors: list[dict[str, float]]
    manifest: dict[str, Any]

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunk_ids": self.chunk_ids,
            "idf": self.idf,
            "vectors": self.vectors,
            "manifest": self.manifest,
        }
        (index_dir / "tfidf_index.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, index_dir: Path) -> "TfidfIndex":
        raw = json.loads((index_dir / "tfidf_index.json").read_text(encoding="utf-8"))
        return cls(
            chunk_ids=list(raw["chunk_ids"]),
            idf={str(k): float(v) for k, v in raw["idf"].items()},
            vectors=[{str(k): float(v) for k, v in row.items()} for row in raw["vectors"]],
            manifest=dict(raw["manifest"]),
        )


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    vec: dict[str, float] = {}
    for term, count in counts.items():
        tf = count / total
        vec[term] = tf * idf.get(term, 0.0)
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def build_tfidf_index(chunks: list[dict[str, Any]], *, corpus_version: str) -> TfidfIndex:
    docs_tokens = [tokenize(str(c.get("text_for_embedding", ""))) for c in chunks]
    df: Counter[str] = Counter()
    for tokens in docs_tokens:
        df.update(set(tokens))
    n_docs = len(chunks) or 1
    idf = {term: math.log((1 + n_docs) / (1 + freq)) + 1.0 for term, freq in df.items()}
    vectors = [_tfidf_vector(tokens, idf) for tokens in docs_tokens]
    manifest = {
        "corpus_version": corpus_version,
        "retriever_type": "tfidf",
        "chunk_count": len(chunks),
        "vocab_size": len(idf),
    }
    return TfidfIndex(
        chunk_ids=[str(c["chunk_id"]) for c in chunks],
        idf=idf,
        vectors=vectors,
        manifest=manifest,
    )


def cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())
