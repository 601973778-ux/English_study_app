from __future__ import annotations

from typing import Any

from Spoken_model.rag.retrieval.retriever import SpokenRagRetriever


class TfidfKnowledgeRetriever:
    def __init__(self) -> None:
        self._inner = SpokenRagRetriever()

    def retrieve(self, query: str, *, filters: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
        try:
            return self._inner.retrieve(
                query,
                top_k=top_k,
                scenario_tags=filters.get("scenario_tags"),
                chunk_types=filters.get("chunk_types"),
                topic_id=filters.get("topic_id"),
            )
        except (FileNotFoundError, OSError):
            return []
