from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .freshness import (
    cache_age_budget_days,
    cache_age_days,
    cadence_label,
    observation_age_budget_days,
    observation_age_days,
)
from .models import DecisionCard


DEFAULT_POLICY: dict[str, Any] = {
    "minimum_evidence_count": 3,
    "minimum_verified_evidence": 0,
    "minimum_source_evidence": 0,
    "minimum_non_english_evidence": 1,
    "require_private_domain_hook": True,
    "require_failure_condition": True,
    "confidence_penalty": 0.0,
    # Promotion floor: average card confidence required before a validated
    # experiment may release capital. A dock only changes an outcome when there
    # is a threshold to fall below, so this key is what gives
    # ``confidence_penalty`` teeth. 0 disables the check.
    "minimum_evidence_confidence": 0.0,
    # Observation budget: how old an observed fact may be. Raised per source by
    # its declared release cadence, so a monthly or annual series is not judged
    # with a daily source's threshold.
    "maximum_evidence_age_days": 45,
    "source_publication_grace_days": 15,
    # Cache budget: how old our local snapshot may be before it must be
    # re-fetched. Independent of how old the observations inside it are.
    "maximum_cache_age_days": 90,
    "cache_refresh_tolerance": 3,
    "minimum_recent_evidence": 0,
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
        checks += 9
        if len(card.evidences) < int(policy["minimum_evidence_count"]):
            failures.append(f"{card.card_id}: missing evidence")
        verified_count = sum(evidence.verified for evidence in card.evidences)
        if verified_count < int(policy.get("minimum_verified_evidence", 0)):
            failures.append(f"{card.card_id}: insufficient verified evidence")
        source_count = sum(evidence.evidence_kind == "source" for evidence in card.evidences)
        if source_count < int(policy.get("minimum_source_evidence", 0)):
            failures.append(f"{card.card_id}: insufficient primary-source evidence")
        if policy["require_private_domain_hook"] and not card.private_domain_hook.hook_message:
            failures.append(f"{card.card_id}: missing private domain hook")
        if policy["require_failure_condition"] and not card.failure_conditions:
            failures.append(f"{card.card_id}: missing failure condition")
        non_english_count = sum(evidence.language != "en" for evidence in card.evidences)
        if non_english_count < int(policy["minimum_non_english_evidence"]):
            failures.append(f"{card.card_id}: missing non-English evidence")
        recent_evidence = [
            evidence
            for evidence in card.evidences
            if evidence.freshness_class in {"live", "recent"}
        ]
        if len(recent_evidence) < int(policy.get("minimum_recent_evidence", 0)):
            failures.append(f"{card.card_id}: insufficient recent evidence")
        # Two independent clocks. An old observation means the source itself has
        # gone quiet; an old snapshot means we have not re-fetched a source that
        # is publishing on schedule. The second is an operational failure and is
        # reported as one, with the remediation the operator needs.
        for evidence in recent_evidence:
            age = observation_age_days(evidence, now)
            budget = observation_age_budget_days(evidence, policy)
            if age > budget:
                failures.append(
                    f"{card.card_id}: stale observation from {evidence.source_name} "
                    f"（观测 {age} 天前，超出 {budget} 天预算；来源节奏：{cadence_label(evidence.source_name)}）"
                )
        for evidence in card.evidences:
            age = cache_age_days(evidence, now)
            budget = cache_age_budget_days(evidence, policy)
            if age > budget:
                failures.append(
                    f"{card.card_id}: expired local cache for {evidence.source_name} "
                    f"（本地快照 {age} 天前，超出 {budget} 天预算；请重跑 datasets 下载脚本）"
                )
        penalty = float(policy.get("confidence_penalty", 0.0))
        adjusted.append(
            card.model_copy(
                update={
                    # Rounded so a docked score serializes as 0.68, not
                    # 0.6799999999999999, in the API payload an operator reads.
                    "confidence_score": round(max(0.0, card.confidence_score - penalty), 4)
                }
            )
        )
    return GateOutcome(not failures, adjusted, failures, checks)
