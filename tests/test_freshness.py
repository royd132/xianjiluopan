"""The decision gate measures two different clocks, and must not conflate them."""

from datetime import datetime, timedelta, timezone

from foresight.models import (
    CardType,
    ConfidenceLevel,
    DecisionCard,
    EvidenceItem,
    FailureCondition,
    PrivateDomainHook,
)
from foresight.policy import DEFAULT_POLICY, evaluate_decision_cards

NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)

POLICY = {
    **DEFAULT_POLICY,
    "minimum_non_english_evidence": 0,
    "minimum_recent_evidence": 1,
}


def _evidence(
    source_name,
    source_type,
    *,
    observed_days_ago=None,
    collected_days_ago=1,
    freshness_class="historical",
    language="en",
):
    return EvidenceItem(
        source_name=source_name,
        source_type=source_type,
        claim="claim",
        raw_value="value",
        language=language,
        collected_at=NOW - timedelta(days=collected_days_ago),
        observed_at=(
            None if observed_days_ago is None else NOW - timedelta(days=observed_days_ago)
        ),
        freshness_class=freshness_class,
        confidence=0.9,
    )


def _background_evidence():
    """Two evidences that never enter the recency or cache budgets."""

    return [
        _evidence(
            "Amazon Reviews 2023 · review sample",
            "review",
            observed_days_ago=900,
            freshness_class="historical",
        ),
        _evidence(
            "UN Comtrade local cache · BR",
            "customs",
            observed_days_ago=300,
            freshness_class="structural",
        ),
    ]


def _card(evidence):
    return DecisionCard(
        card_id="card-freshness",
        card_type=CardType.PRODUCT_SELECTION,
        action_title="title",
        action_detail="detail",
        confidence=ConfidenceLevel.HIGH,
        confidence_score=0.9,
        evidences=[evidence, *_background_evidence()],
        private_domain_hook=PrivateDomainHook(
            seed_audience="audience", channel="channel", hook_message="hook"
        ),
        failure_conditions=[
            FailureCondition(
                condition="condition",
                metric_to_watch="metric",
                threshold="threshold",
                action_on_trigger="watch",
            )
        ],
        data_sources=["dataset"],
        collection_timestamp=NOW,
    )


def _evaluate(evidence, policy=None):
    return evaluate_decision_cards([_card(evidence)], policy or POLICY, now=NOW)


def test_monthly_source_lag_is_not_reported_as_stale():
    """GSCPI publishes about a month after its reference period.

    Its newest observation is already ~30 days old when it lands, so a flat
    45-day recency threshold rejects a healthy source ~45 days after every
    release. This is the failure that made real mode unusable.
    """

    outcome = _evaluate(
        _evidence(
            "Federal Reserve Bank of New York · GSCPI",
            "shipping",
            observed_days_ago=56,
            freshness_class="recent",
        )
    )

    assert outcome.accepted, outcome.failures


def test_daily_source_with_the_same_age_is_still_stale():
    """The allowance is per source cadence, not a blanket relaxation."""

    outcome = _evaluate(
        _evidence(
            "ECB reference rates via Frankfurter",
            "fx",
            observed_days_ago=56,
            freshness_class="live",
        )
    )

    assert not outcome.accepted
    assert any("stale observation" in failure for failure in outcome.failures)
    assert any("ECB 参考汇率" in failure for failure in outcome.failures)


def test_cadence_allowance_does_not_hide_an_abandoned_source():
    """A monthly source that has not moved in months is a real signal failure."""

    outcome = _evaluate(
        _evidence(
            "Federal Reserve Bank of New York · GSCPI",
            "shipping",
            observed_days_ago=200,
            freshness_class="recent",
        )
    )

    assert not outcome.accepted
    assert any("stale observation" in failure for failure in outcome.failures)


def test_expired_cache_is_reported_as_an_operational_failure():
    """An ancient local snapshot gets its own message and its own remedy."""

    outcome = _evaluate(
        _evidence(
            "Replay source 0",
            "review",
            observed_days_ago=200,
            collected_days_ago=200,
            freshness_class="unknown",
        )
    )

    assert not outcome.accepted
    assert any("expired local cache" in failure for failure in outcome.failures)
    assert any("下载脚本" in failure for failure in outcome.failures)
    assert not any("stale observation" in failure for failure in outcome.failures)


def test_unregistered_source_keeps_the_policy_floor():
    outcome = _evaluate(
        _evidence(
            "Some unregistered feed",
            "social",
            observed_days_ago=50,
            freshness_class="live",
        )
    )

    assert not outcome.accepted
    assert any("stale observation" in failure for failure in outcome.failures)


def test_policy_can_never_demand_data_fresher_than_the_source_publishes():
    """Tightening the floor below the cadence allowance has no effect.

    The floor is a minimum standard, not a way to wish a monthly series into
    being daily. Callers that want to exclude a lagging source should raise
    ``minimum_recent_evidence`` or drop the source instead.
    """

    tightened = {**POLICY, "maximum_evidence_age_days": 10}
    outcome = _evaluate(
        _evidence(
            "Federal Reserve Bank of New York · GSCPI",
            "shipping",
            observed_days_ago=56,
            freshness_class="recent",
        ),
        tightened,
    )

    assert outcome.accepted, outcome.failures


def test_policy_persisted_before_the_new_keys_existed_still_evaluates():
    """Policies stored in the version table are not migrated, so read defensively."""

    legacy = {
        "minimum_evidence_count": 3,
        "minimum_verified_evidence": 0,
        "minimum_source_evidence": 0,
        "minimum_non_english_evidence": 0,
        "require_private_domain_hook": True,
        "require_failure_condition": True,
        "confidence_penalty": 0.0,
        "maximum_evidence_age_days": 45,
        "minimum_recent_evidence": 1,
    }

    outcome = _evaluate(
        _evidence(
            "Federal Reserve Bank of New York · GSCPI",
            "shipping",
            observed_days_ago=56,
            freshness_class="recent",
        ),
        legacy,
    )

    assert outcome.accepted, outcome.failures
