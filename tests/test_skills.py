import asyncio
import json

import pytest

from foresight.models import ResearchRequest, ReviewRequest
from foresight.policy import DEFAULT_POLICY
from foresight.runtime import ForesightRuntime
from foresight.skills import (
    SkillArtifact,
    SkillBank,
    SkillRetrieval,
    SkillStore,
    SkillTrigger,
    load_seed_skills,
)


# ---------------------------------------------------------------------------
# SkillArtifact model tests
# ---------------------------------------------------------------------------


def test_skill_artifact_fingerprint_is_stable():
    skill = SkillArtifact(
        name="test-skill",
        description="A test skill",
        triggers=[SkillTrigger(keyword="test", weight=1.0)],
    )
    fp1 = skill.fingerprint()
    fp2 = skill.fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 16


def test_skill_artifact_matches_market_and_category():
    skill = SkillArtifact(
        name="br-pricing",
        description="BR pricing skill",
        scope_markets=["BR"],
        scope_categories=["pet feeder", "coffee"],
    )
    assert skill.matches_market("BR")
    assert skill.matches_market("br")
    assert not skill.matches_market("US")

    skill_wildcard = SkillArtifact(
        name="global",
        description="Global skill",
        scope_markets=["*"],
        scope_categories=["*"],
    )
    assert skill_wildcard.matches_market("US")
    assert skill_wildcard.matches_category("anything")

    assert skill.matches_category("pet feeder")
    assert skill.matches_category("Automatic Pet Feeder")
    assert not skill.matches_category("bluetooth earbuds")


# ---------------------------------------------------------------------------
# SkillStore persistence tests
# ---------------------------------------------------------------------------


def test_skill_store_save_and_retrieve(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    skill = SkillArtifact(
        name="test-skill",
        description="A test skill",
        triggers=[SkillTrigger(keyword="test")],
        body="# Test body",
    )
    store.save(skill)

    loaded = store.get(skill.skill_id)
    assert loaded is not None
    assert loaded.name == "test-skill"
    assert loaded.body == "# Test body"
    assert len(loaded.triggers) == 1


def test_skill_store_list_and_filter(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    for name, status in [("a", "candidate"), ("b", "active"), ("c", "ready")]:
        store.save(SkillArtifact(name=name, description=f"skill {name}", status=status))

    all_skills = store.list_all()
    assert len(all_skills) == 3

    active = store.list_active()
    assert len(active) == 1
    assert active[0].name == "b"


def test_skill_store_activate_and_rollback(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    v1 = SkillArtifact(name="price-check", description="v1", version="0.1.0", status="ready")
    store.save(v1)
    store.activate(v1.skill_id)

    v2 = SkillArtifact(
        name="price-check",
        description="v2",
        version="0.2.0",
        status="ready",
        parent_id=v1.skill_id,
    )
    store.save(v2)
    store.activate(v2.skill_id)

    active = store.list_active()
    assert len(active) == 1
    assert active[0].version == "0.2.0"

    rolled_back = store.rollback("price-check")
    assert rolled_back.version == "0.1.0"
    assert store.list_active()[0].version == "0.1.0"


def test_skill_store_activate_rejects_non_ready(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    skill = SkillArtifact(name="test", description="test", status="candidate")
    store.save(skill)
    with pytest.raises(ValueError, match="not passed evaluation"):
        store.activate(skill.skill_id)


def test_skill_store_evaluation_recording(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    skill = SkillArtifact(name="test", description="test")
    store.save(skill)

    record = {
        "eval_id": "eval-001",
        "skill_id": skill.skill_id,
        "split": "validation",
        "metrics": {"accuracy": 0.85, "improvement": 0.05},
        "decision": "ready",
    }
    store.record_evaluation(record)

    evals = store.list_evaluations(skill.skill_id)
    assert len(evals) == 1
    assert evals[0]["decision"] == "ready"


# ---------------------------------------------------------------------------
# BM25 Retrieval tests
# ---------------------------------------------------------------------------


def test_retrieval_returns_scored_results():
    retrieval = SkillRetrieval()
    skills = [
        SkillArtifact(
            name="price-margin-safety",
            description="Cross-market margin safety check for pricing",
            triggers=[
                SkillTrigger(keyword="pricing", weight=2.0),
                SkillTrigger(keyword="margin", weight=1.5),
            ],
        ),
        SkillArtifact(
            name="market-entry-evidence",
            description="Evidence completeness check for new markets",
            triggers=[
                SkillTrigger(keyword="market", weight=2.0),
                SkillTrigger(keyword="evidence", weight=1.5),
            ],
        ),
    ]

    results = retrieval.search("pricing margin cost", skills)
    assert len(results) > 0
    assert results[0][0].name == "price-margin-safety"
    assert results[0][1] > 0


def test_retrieval_respects_min_score():
    retrieval = SkillRetrieval()
    skills = [
        SkillArtifact(
            name="unrelated",
            description="Completely unrelated skill",
            triggers=[SkillTrigger(keyword="astronomy", weight=1.0)],
        ),
    ]
    results = retrieval.search("pricing margin", skills, min_score=0.1)
    assert len(results) == 0


def test_retrieval_handles_chinese_keywords():
    retrieval = SkillRetrieval()
    skills = [
        SkillArtifact(
            name="pricing-cn",
            description="定价策略安全检查",
            triggers=[
                SkillTrigger(keyword="定价", weight=2.0),
                SkillTrigger(keyword="毛利", weight=1.5),
            ],
        ),
    ]
    results = retrieval.search("定价 毛利", skills)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# SkillBank lifecycle tests
# ---------------------------------------------------------------------------


def test_skill_bank_loads_seed_skills(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    loaded = load_seed_skills(store)
    assert len(loaded) >= 4

    names = {s.name for s in loaded}
    assert "market-entry-evidence-check" in names
    assert "price-margin-safety" in names
    assert "review-pain-localization" in names
    assert "stale-signal-recompute" in names


def test_skill_bank_seed_deduplication(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    first = load_seed_skills(store)
    second = load_seed_skills(store)
    assert len(first) >= 4
    assert len(second) == 0


def test_skill_bank_retrieve_for_research(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    load_seed_skills(store)
    bank = SkillBank(store)

    # Promote all seeds so they're retrievable
    for skill in store.list_all():
        store.save(skill.model_copy(update={"status": "ready"}))
        store.activate(skill.skill_id)

    # Use a query that overlaps with seed skill triggers
    results = bank.retrieve("pricing margin evidence", market="BR", category="pet feeder")
    assert len(results) > 0
    assert all(isinstance(score, float) for _, score in results)

    # Also test retrieve_for_research convenience method
    formatted = bank.retrieve_for_research("pricing margin", "BR")
    assert isinstance(formatted, list)


def test_skill_bank_extract_candidate_from_feedback(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    bank = SkillBank(store)

    feedback = {
        "feedback_id": "fb-001",
        "feedback_type": "rejected",
        "failure_type": "weak_evidence",
        "reason": "Evidence coverage is insufficient for target market",
    }
    card = {
        "card_type": "product_selection",
        "card_id": "card-001",
    }

    skill = bank.extract_candidate_from_feedback(feedback, card)
    assert skill is not None
    assert skill.status == "candidate"
    assert skill.source_feedback_id == "fb-001"
    assert "evidence" in [t.keyword for t in skill.triggers]


def test_skill_bank_extract_merges_on_same_name(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    bank = SkillBank(store)

    for idx in range(2):
        feedback = {
            "feedback_id": f"fb-{idx}",
            "feedback_type": "rejected",
            "failure_type": "weak_evidence",
            "reason": f"Insufficient evidence round {idx}",
        }
        card = {"card_type": "pricing", "card_id": f"card-{idx}"}
        bank.extract_candidate_from_feedback(feedback, card)

    all_skills = store.list_all()
    pricing_skills = [s for s in all_skills if "price-margin-safety" in s.name]
    assert len(pricing_skills) >= 1
    if len(pricing_skills) > 1:
        versions = {s.version for s in pricing_skills}
        assert len(versions) > 1


def test_skill_bank_evaluate_candidate(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    load_seed_skills(store)
    bank = SkillBank(store)

    candidates = [s for s in store.list_all() if s.status == "candidate"]
    assert len(candidates) > 0

    record = bank.evaluate_candidate(candidates[0].skill_id)
    assert record["decision"] in ("ready", "rejected")
    assert "validation" in record["metrics"]
    assert "holdout" in record["metrics"]


def test_skill_bank_promote_and_rollback(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    bank = SkillBank(store)

    skill = SkillArtifact(
        name="test-promote",
        description="Test promotion",
        triggers=[SkillTrigger(keyword="test")],
        status="ready",
    )
    store.save(skill)

    promoted = bank.promote(skill.skill_id)
    assert promoted.status == "active"

    # Create a child version
    v2 = SkillArtifact(
        name="test-promote",
        description="v2",
        version="0.2.0",
        triggers=[SkillTrigger(keyword="test")],
        status="ready",
        parent_id=skill.skill_id,
    )
    store.save(v2)
    bank.promote(v2.skill_id)

    assert store.list_active()[0].version == "0.2.0"
    # Two versions of the name now exist, so status() must advertise it as
    # rollbackable — that is what enables the operator's rollback button.
    assert bank.status()["rollbackable_names"] == ["test-promote"]

    rolled_back = bank.rollback_skill("test-promote")
    assert rolled_back.version == "0.1.0"


def test_skill_bank_promote_rejects_non_ready(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    bank = SkillBank(store)

    skill = SkillArtifact(
        name="not-ready",
        description="Not ready",
        triggers=[SkillTrigger(keyword="test")],
        status="candidate",
    )
    store.save(skill)

    with pytest.raises(ValueError, match="must be 'ready'"):
        bank.promote(skill.skill_id)


def test_skill_bank_status(tmp_path):
    store = SkillStore(tmp_path / "skills.db")
    load_seed_skills(store)
    bank = SkillBank(store)

    status = bank.status()
    assert status["total_skills"] >= 4
    assert status["candidate_count"] >= 4
    assert status["active_count"] == 0
    # Nothing has been activated yet, so no name has a parent to roll back to.
    assert status["rollbackable_names"] == []


# ---------------------------------------------------------------------------
# Integration: skills wire into runtime
# ---------------------------------------------------------------------------


def test_runtime_initializes_skill_bank(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")
    assert runtime.skills is not None
    status = runtime.skills.status()
    assert status["total_skills"] >= 4


def test_runtime_rejected_card_extracts_skill_candidate(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

        skill_before = runtime.skills.status()["total_skills"]
        runtime.review_card(
            result.cards[0].card_id,
            ReviewRequest(
                status="rejected",
                reviewer="tester",
                reason="Weak evidence for target market",
                failure_type="weak_evidence",
            ),
        )

        skill_after = runtime.skills.status()["total_skills"]
        assert skill_after > skill_before

    asyncio.run(scenario())


def test_runtime_retrieved_skills_appear_in_card_data(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")

        # Promote all seed skills so they're retrievable
        for skill in runtime.skill_store.list_all():
            runtime.skill_store.save(skill.model_copy(update={"status": "ready"}))
            runtime.skill_store.activate(skill.skill_id)

        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

        # Check that retrieved_skills are in card_specific_data
        for card in result.cards:
            retrieved = card.card_specific_data.get("retrieved_skills", [])
            # An empty list satisfied this assertion for as long as the query was
            # the product name, which is how a dead injection path stayed green.
            assert retrieved, "a promoted seed skill must be retrieved for the demo run"
            assert all(item["skill_id"] and item["version"] for item in retrieved)

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Injection: a retrieved skill has to change the run, not decorate it
# ---------------------------------------------------------------------------


def test_retrieval_matches_the_decision_context_not_the_product_name(tmp_path):
    """A run retrieves against the decisions it is about to make, not the product.

    "pet feeder BR" is a token match against nothing — no decision check is scoped
    to a product — so the bank was wired into the pipeline and never reached.
    """
    store = SkillStore(tmp_path / "skills.db")
    load_seed_skills(store)
    bank = SkillBank(store)
    for skill in store.list_all():
        store.save(skill.model_copy(update={"status": "ready"}))
        store.activate(skill.skill_id)

    hits = bank.retrieve_for_research("pet feeder", "BR")
    assert hits, "the demo research context must retrieve the seed decision checks"
    assert all(hit["retrieval_score"] > 0 for hit in hits)
    # Injection needs something to execute, and the body has to travel with it
    # for an operator to be able to read why the check exists.
    assert any(hit["evidence_policy"] for hit in hits)
    assert all(hit["body"] for hit in hits)
    scores = [hit["retrieval_score"] for hit in hits]
    assert scores == sorted(scores, reverse=True), "the top-k window must be ranked"


def test_profile_bound_directives_are_deferred_in_mock_runs(tmp_path):
    """A primary-source requirement cannot execute in a profile that collects no
    primary sources. It is recorded as deferred, never silently enforced or lost."""
    bank = SkillBank(SkillStore(tmp_path / "skills.db"))
    retrieved = [
        {
            "name": "market-entry-evidence-check",
            "version": "0.1.0",
            "evidence_policy": "require_minimum_source_evidence:2;require_max_evidence_age_days:30",
        }
    ]

    mock_policy = dict(DEFAULT_POLICY)
    patch = bank.apply_evidence_policies(retrieved, mock_policy, "mock")
    assert mock_policy["maximum_evidence_age_days"] == 30
    assert mock_policy["minimum_source_evidence"] == DEFAULT_POLICY["minimum_source_evidence"]
    assert list(patch["deferred"]) == ["market-entry-evidence-check@0.1.0"]
    assert "mock-structure" in patch["deferred"]["market-entry-evidence-check@0.1.0"][0]

    real_policy = dict(DEFAULT_POLICY)
    real_patch = bank.apply_evidence_policies(retrieved, real_policy, "real")
    assert real_policy["minimum_source_evidence"] == 2
    assert real_patch["deferred"] == {}


def test_a_retrieved_skill_changes_the_run_it_is_injected_into(tmp_path):
    """The whole claim in one test: an active skill reaches the gate and the card.

    Nothing is promoted by default, so the demo run is unchanged; once the seed
    checks are active their directives are merged into the run's fingerprinted
    policy, the gate docks every card, and the card carries the check.
    """
    async def scenario(activate: bool):
        runtime = ForesightRuntime(tmp_path / f".foresight-{activate}")
        if activate:
            for skill in runtime.skill_store.list_all():
                runtime.skill_store.save(skill.model_copy(update={"status": "ready"}))
                runtime.skill_store.activate(skill.skill_id)
        return runtime, await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

    _, before = asyncio.run(scenario(False))
    assert before.cards[0].card_specific_data["applied_skill_checks"] == {}
    assert not any("Skill" in item for item in before.contract.stop_conditions)

    runtime, after = asyncio.run(scenario(True))
    card = after.cards[0]
    applied = card.card_specific_data["applied_skill_checks"]
    assert applied, "a retrieved skill's directives must be merged, not just listed"
    assert card.card_specific_data["deferred_skill_checks"], (
        "the primary-source directive has to be recorded as deferred in a mock run"
    )
    # The dock is the visible half of injection: every published card carries it.
    for plain, injected in zip(before.cards, after.cards):
        assert round(plain.confidence_score - injected.confidence_score, 4) == 0.05
    assert any("Skill 自检未达阈值" in item for item in after.contract.stop_conditions)
    assert any("Skill" in basis for basis in after.contract.core_basis)
    # Injection tightens the gate; it does not turn the demo run into a failure.
    assert after.contract.verdict == before.contract.verdict
    # And it is inside the run's fingerprinted policy, not applied beside it.
    run_policy = runtime.component_snapshot(after.task_id)["policy"]
    assert run_policy["policy"]["confidence_penalty"] == 0.05
    assert run_policy["skill_patch"]["applied"] == applied


def test_skill_evaluation_measures_against_the_parent_version(tmp_path):
    """A new version has to beat the version it replaces.

    Measured against the bare default instead — which is what the eval record
    claimed was happening while it always evaluated ``DEFAULT_POLICY`` — a child
    that drops its parent's staleness check scored as an improvement.
    """
    store = SkillStore(tmp_path / "skills.db")
    bank = SkillBank(store)
    parent = SkillArtifact(
        name="stale-signal-recompute",
        description="v1",
        version="0.1.0",
        evidence_policy="require_max_evidence_age_days:30",
        status="ready",
    )
    store.save(parent)
    child = SkillArtifact(
        name="stale-signal-recompute",
        description="v2 drops the staleness check",
        version="0.2.0",
        evidence_policy="require_minimum_source_evidence:3",
        status="candidate",
        parent_id=parent.skill_id,
    )
    store.save(child)

    record = bank.evaluate_candidate(child.skill_id)
    assert record["baseline_skill_id"] == parent.skill_id
    assert record["metrics"]["holdout"]["improvement"] < 0
    assert record["decision"] == "rejected"
    assert store.get(child.skill_id).status == "rejected"

    # A first version has no parent, so it is measured against the default policy
    # — and that is recorded as such rather than claimed as a parent comparison.
    orphan = SkillArtifact(
        name="market-entry-evidence-check",
        description="first version",
        version="0.1.0",
        evidence_policy="require_minimum_source_evidence:3",
        status="candidate",
    )
    store.save(orphan)
    orphan_record = bank.evaluate_candidate(orphan.skill_id)
    assert orphan_record["baseline_skill_id"] is None
    assert orphan_record["decision"] == "ready"
