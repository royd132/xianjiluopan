from __future__ import annotations

from collections import Counter
from typing import Any

from .harness import MemoryStore
from .models import FeedbackRecord


class FeedbackFlywheel:
    """Layer 1/2 evolution: collect feedback and distill reusable memory."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def record(self, feedback: FeedbackRecord, card: dict[str, Any]) -> None:
        payload = feedback.model_dump(mode="json")
        self.memory.append_feedback(payload)
        namespace = "positive_cases" if feedback.feedback_type == "approved" else "negative_cases"
        self.memory.put(namespace, feedback.feedback_id, {"feedback": payload, "card": card})

    def distill_patterns(self, feedback_rows: list[dict[str, Any]]) -> dict[str, Any]:
        counts = Counter(row["feedback_type"] for row in feedback_rows)
        total = sum(counts.values()) or 1
        return {
            "feedback_count": total,
            "approval_rate": counts["approved"] / total,
            "dominant_signal": counts.most_common(1)[0][0] if counts else "none",
        }
