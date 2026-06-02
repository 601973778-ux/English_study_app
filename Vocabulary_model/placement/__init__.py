"""词汇水平评估：方案 B 自适应 + 四选一（1 个 LLM 形近词释义干扰项）。"""

from Vocabulary_model.placement.service import (
    apply_recommendation_to_settings,
    grade_answer,
    start_placement,
    submit_answer,
)

__all__ = [
    "start_placement",
    "submit_answer",
    "grade_answer",
    "apply_recommendation_to_settings",
]
