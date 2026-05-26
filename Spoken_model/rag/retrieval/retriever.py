from __future__ import annotations

from typing import Any

from Spoken_model.rag.build_kb import search as _search


class SpokenRagRetriever:
    """Lightweight retriever over local TF-IDF index."""

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        scenario_tags: list[str] | None = None,
        chunk_types: list[str] | None = None,
        topic_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return _search(
            query,
            top_k=top_k,
            scenario_tags=scenario_tags,
            chunk_types=chunk_types,
            topic_id=topic_id,
        )
