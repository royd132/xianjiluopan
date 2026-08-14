from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import DecisionCard


DEFAULT_POLICY: dict[str, Any] = {
    "minimum_evidence_count": 3,
    "minimum_non_english_evidence": 1,
    "require_private_domain_hook": True,
    "require_failure_condition": True,
    "confidence_penalty": 0.0,
    "maximum_evidence_age_days": 45,
}


@dataclass(slots=True)
class GateOutcome:
    accepted: bool
    cards: list[DecisionCard]
    failures: list[str]
    checks: int


def evaluate_decision_cards(
    cards: Iterable[DecisionCard],
    policy: dict[str, Any],
    now: datetime | None = None,
) -> GateOutcome:
    """Production decision gate shared by live runs and offline replay."""

    now = now or datetime.now(timezone.utc)
    failures: list[str] = []
    adjusted: list[DecisionCard] = []
    checks = 0
    for card in cards:
        checks += 5
        if len(card.evidences) < int(policy["minimum_evidence_count"]):
            failures.append(f"{card.card_id}: missing evidence")
        if policy["require_private_domain_hook"] and not card.private_domain_hook.hook_message:
            failures.append(f"{card.card_id}: missing private domain hook")
        if policy["require_failure_condition"] and not card.failure_conditions:
            failures.append(f"{card.card_id}: missing failure condition")
        non_english_count = sum(evidence.language != "en" for evidence in card.evidences)
        if non_english_count < int(policy["minimum_non_english_evidence"]):
            failures.append(f"{card.card_id}: missing non-English evidence")
        evidence_age = max((now - evidence.collected_at).days for evidence in card.evidences)
        if evidence_age > int(policy["maximum_evidence_age_days"]):
            failures.append(f"{card.card_id}: stale evidence")
        penalty = float(policy.get("confidence_penalty", 0.0))
        adjusted.append(
            card.model_copy(update={"confidence_score": max(0.0, card.confidence_score - penalty)})
        )
    return GateOutcome(not failures, adjusted, failures, checks)
