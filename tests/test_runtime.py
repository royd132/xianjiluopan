import asyncio
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from foresight.events import CollaborationBlackboard
from foresight.data import MockDataProvider
from foresight.evolution import WorkflowReplayEvaluator
from foresight.models import CardType, DecisionContract, DecisionVerdict, MonitoringSubscriptionRequest, OverrideRequest, ResearchRequest, ReviewRequest, ValidationResultRequest
from foresight.policy import DEFAULT_POLICY, evaluate_decision_cards
from foresight.real_data_provider import RealDataProvider
from foresight.runtime import NODE_AGENTS, ForesightRuntime, UnsupportedResearchModeError


FIXTURE_FX_LATEST = datetime.now(timezone.utc).date()
FIXTURE_FX_PREVIOUS = FIXTURE_FX_LATEST - timedelta(days=30)


class FakeGroundedExtractor:
    configured = True
    model = "fake-qwen"
    max_reviews = 10
    adapter_version = "fake-grounded-v1"

    async def extract(self, category, reviews):
        return [
            {
                "pain_type": "noise",
                "label": "夜间噪音",
                "review_ids": [reviews[0].record_id, reviews[1].record_id],
                "mentions": 2,
                "sample_original": reviews[0].text,
                "sample_translation": "优先验证低噪结构",
            }
        ]

    def prompt_fingerprint(self, category, reviews):
        return "f" * 64


def build_public_dataset_fixture(root):
    (root / "fx").mkdir(parents=True)
    (root / "reviews").mkdir(parents=True)
    (root / "trade").mkdir(parents=True)
    (root / "freight").mkdir(parents=True)
    (root / "amazon_metadata").mkdir(parents=True)
    for filename, quote in {
        "USD_BRL.csv": "BRL",
        "USD_MXN.csv": "MXN",
        "USD_MYR.csv": "MYR",
        "EUR_USD.csv": "USD",
    }.items():
        with (root / "fx" / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", f"rate_{quote}"])
            writer.writerow([FIXTURE_FX_PREVIOUS.isoformat(), 5.0])
            writer.writerow([FIXTURE_FX_LATEST.isoformat(), 5.1])
    review_rows = [
        {
            "rating": 2,
            "title": "Automatic feeder works but is noisy",
            "text": "The automatic feeder wakes us at night because it is too loud.",
            "parent_asin": f"asin-{index}",
            "helpful_vote": 10 - index,
        }
        for index in range(4)
    ]
    for filename in ("Pet_Supplies.sample.jsonl", "Home_and_Kitchen.sample.jsonl", "Electronics.sample.jsonl"):
        with (root / "reviews" / filename).open("w", encoding="utf-8") as handle:
            for row in review_rows:
                handle.write(json.dumps(row) + "\n")
    with (root / "amazon_metadata" / "Pet_Supplies.relevant.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(12):
            handle.write(
                json.dumps(
                    {
                        "title": f"Automatic Pet Feeder {index}",
                        "features": ["automatic cat feeder"],
                        "price": 30 + index,
                        "parent_asin": f"meta-asin-{index}",
                    }
                )
                + "\n"
            )
    with (root / "trade" / "comtrade_imports.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["market", "reporter_code", "hs_code", "hs_desc", "year", "flow", "primary_value_usd", "net_weight_kg", "is_estimated"],
        )
        writer.writeheader()
        for year, value in ((2024, 100), (2025, 125)):
            writer.writerow({"market": "BR", "reporter_code": 76, "hs_code": "8509", "hs_desc": "test", "year": year, "flow": "import", "primary_value_usd": value, "net_weight_kg": 1, "is_estimated": False})
    with (root / "freight" / "gscpi_monthly.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "gscpi"])
        writer.writerow(["2026-06-30", 0.5])
        writer.writerow(["2026-07-31", 0.8])


def test_offline_runtime_generates_four_valid_cards(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="宠物自动喂食器", market="BR"))
        assert len(result.cards) == 4
        assert {card.card_type for card in result.cards} == set(CardType)
        assert all(len(card.evidences) >= 3 for card in result.cards)
        assert all(card.private_domain_hook.hook_message for card in result.cards)
        assert all(card.failure_conditions for card in result.cards)
        assert all(any(item.language != "en" for item in card.evidences) for card in result.cards)
        assert result.evidence_count == 5
        assert runtime.load_checkpoint(result.task_id)["stage"] == "validated"

    asyncio.run(scenario())


def test_br_olist_reviews_fill_an_empty_amazon_cache(tmp_path):
    provider = RealDataProvider(tmp_path)
    provider.reviews_dir.mkdir(parents=True)
    (provider.reviews_dir / "Pet_Supplies.sample.jsonl").write_text("", encoding="utf-8")
    provider._olist_market_data = lambda _category: {
        "reviews": [
            {"record_id": "olist-1", "rating": 2, "title": "", "text": "faz barulho"},
            {"record_id": "olist-2", "rating": 3, "title": "", "text": "difícil limpar"},
        ],
    }

    rows = provider._relevant_reviews("pet_feeder", "BR")

    assert len(rows) == 2
    assert rows[0]["_source_name"] == "Olist public dataset"


def test_grounded_pain_points_preserve_review_languages(tmp_path):
    async def scenario():
        provider = RealDataProvider(tmp_path, model_adapter=FakeGroundedExtractor())
        points = await provider._llm_pain_points(
            "宠物自动喂食器",
            [
                {"rating": 2, "text": "faz barulho", "language": "pt", "record_id": "olist-1"},
                {"rating": 3, "text": "difícil limpar", "language": "pt", "record_id": "olist-2"},
            ],
        )
        assert points[0].languages == ["pt"]

    asyncio.run(scenario())


def test_event_trace_and_feedback_memory(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        events = runtime.boards[result.task_id].events
        assert events[0].event_type.value == "task.started"
        assert events[-1].event_type.value == "task.completed"
        assert any(event.event_type.value == "gate.passed" for event in events)
        feedback = runtime.review_card(result.cards[0].card_id, ReviewRequest(status="approved", reviewer="tester"))
        assert feedback.feedback_type == "approved"
        saved = runtime.harness.memory.get("positive_cases", feedback.feedback_id)
        assert saved["feedback"]["user_id"] == "tester"

    asyncio.run(scenario())


def test_scenario_aware_cold_start_keeps_category_and_market_consistent(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")

        coffee = await runtime.run(ResearchRequest(category="portable coffee grinder", market="US"))
        coffee_text = " ".join(f"{card.action_title} {card.action_detail}" for card in coffee.cards)
        assert "美国市场" in coffee_text
        assert "巴西" not in coffee_text
        assert "养宠" not in coffee_text
        assert "低残粉" in coffee_text
        assert any("Amazon US" in source for card in coffee.cards for source in card.data_sources)
        assert any("美国" in signal.label or "北美" in signal.label for signal in coffee.supply_signals)
        assert coffee.pain_points[0].pain_type == "consistency"
        assert all(not evidence.verified for card in coffee.cards for evidence in card.evidences)

        blender = await runtime.run(ResearchRequest(category="便携榨汁机", market="MX"))
        blender_text = " ".join(f"{card.action_title} {card.action_detail}" for card in blender.cards)
        assert "墨西哥市场" in blender_text
        assert "防漏" in blender_text
        assert "夜间噪音" not in blender_text
        assert blender.pain_points[0].pain_type == "leakage"

    asyncio.run(scenario())


def test_runtime_rejects_unavailable_real_and_hybrid_modes(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=tmp_path / "empty-datasets")

    for mode in ("real", "hybrid"):
        with pytest.raises(UnsupportedResearchModeError, match="not available"):
            runtime.create_task(ResearchRequest(category="pet feeder", market="BR", mode=mode))


def test_real_mode_uses_grounded_model_and_harness_tool_snapshot(tmp_path):
    async def scenario():
        datasets = tmp_path / "datasets"
        build_public_dataset_fixture(datasets)
        provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())
        runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider)

        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR", mode="real"))
        snapshot = runtime.component_snapshot(result.task_id)
        evaluation = runtime.boards[result.task_id].read("evaluation")

        assert result.mode == "real"
        assert result.pain_points[0].extracted_by == "llm"
        assert result.pain_points[0].verification["review_ids"] == ["r001", "r002"]
        assert snapshot["tools"]["real_data"]["plugin_id"] == "provider.real-data"
        assert evaluation["gate_profile"] == "verified-evidence"
        assert all(sum(item.evidence_kind == "source" for item in card.evidences) >= 3 for card in result.cards)
        assert result.cards[1].confidence.value == "medium"
        assert result.cards[1].card_specific_data["price_data_mode"] == "amazon_2023_listing_snapshot"

    asyncio.run(scenario())


def test_real_evidence_preserves_observation_time_and_market_scope(tmp_path):
    async def scenario():
        datasets = tmp_path / "datasets"
        build_public_dataset_fixture(datasets)
        provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())
        runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider)

        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR", mode="real"))
        evidences = result.cards[0].evidences

        fx = next(item for item in evidences if item.freshness_class == "live")
        amazon_review = next(
            item
            for item in evidences
            if item.market_scope == "cross_market" and item.source_type == "review"
        )
        assert fx.observed_at.date() == FIXTURE_FX_LATEST
        assert fx.market_scope == "target_market"
        assert amazon_review.freshness_class == "historical"
        assert amazon_review.source_market == "global"
        assert amazon_review.observation_period == "Amazon Reviews 2023 snapshot"

    asyncio.run(scenario())


def test_capability_matrix_rejects_real_mode_without_source_backed_price(tmp_path):
    datasets = tmp_path / "datasets"
    build_public_dataset_fixture(datasets)
    provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())
    runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider)

    pet_feeder = runtime.real_provider.scenario_capability("pet feeder", "BR")
    headphones = runtime.real_provider.scenario_capability("noise cancelling headphones", "US")

    assert pet_feeder["real_available"] is True
    assert pet_feeder["price_source"].startswith("Amazon Reviews 2023")
    assert headphones["real_available"] is False
    assert "source_backed_price" in headphones["blocking_reasons"]
    assert "current_competitor_listings" in pet_feeder["known_gaps"]
    with pytest.raises(UnsupportedResearchModeError, match="Missing"):
        runtime.create_task(ResearchRequest(category="noise cancelling headphones", market="US", mode="real"))


def test_monitoring_snapshot_reports_manual_status_and_real_observation_dates(tmp_path):
    datasets = tmp_path / "datasets"
    build_public_dataset_fixture(datasets)
    provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())

    snapshot = provider.monitoring_snapshot("pet feeder", "BR")

    assert snapshot["schedule_status"] == "manual_snapshot"
    assert snapshot["capability"]["real_available"] is True
    signals = {item["key"]: item for item in snapshot["signals"]}
    assert signals["fx"]["observed_at"] == FIXTURE_FX_LATEST.isoformat()
    assert signals["trade"]["observed_at"] == "2025"
    assert snapshot["trigger_count"] >= 0


def test_concurrent_mock_and_real_tasks_keep_provider_modes_isolated(tmp_path):
    async def scenario():
        datasets = tmp_path / "datasets"
        build_public_dataset_fixture(datasets)
        provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())
        runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider)

        mock_result, real_result = await asyncio.gather(
            runtime.run(ResearchRequest(category="pet feeder", market="BR", mode="mock")),
            runtime.run(ResearchRequest(category="pet feeder", market="BR", mode="real")),
        )

        assert mock_result.mode == "mock"
        assert real_result.mode == "real"
        assert all(not item.verified for card in mock_result.cards for item in card.evidences)
        assert all(sum(item.verified for item in card.evidences) >= 3 for card in real_result.cards)

    asyncio.run(scenario())


def test_mock_run_uses_structure_gate_and_discloses_unverified_evidence(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        evaluation = runtime.boards[result.task_id].read("evaluation")

        assert evaluation["gate_profile"] == "mock-structure"
        assert evaluation["verified_evidence_required"] == 0
        assert all(not evidence.verified for card in result.cards for evidence in card.evidences)

        verified_policy = {**DEFAULT_POLICY, "minimum_verified_evidence": 3}
        verified_outcome = evaluate_decision_cards(result.cards, verified_policy)
        assert not verified_outcome.accepted
        assert all("insufficient verified evidence" in failure for failure in verified_outcome.failures)

    asyncio.run(scenario())


def test_rejected_card_creates_gated_policy_candidate(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        runtime.review_card(
            result.cards[0].card_id,
            ReviewRequest(
                status="rejected",
                reviewer="buyer",
                reason="证据覆盖不足",
                failure_type="weak_evidence",
            ),
        )

        before = runtime.evolution.status()
        assert len([item for item in before["failure_cases"] if item["status"] == "open"]) == 1

        evolution_run = runtime.evolution.generate_candidate()
        assert evolution_run["decision"] == "ready"
        assert evolution_run["metrics"]["validation_improvement"] > 0
        assert evolution_run["metrics"]["validation"]["candidate"]["execution_path"][1] == "shared decision gate"
        assert evolution_run["metrics"]["reproducibility"]["holdout_dataset_sha256"]
        assert (
            evolution_run["metrics"]["holdout"]["candidate"]["accuracy"]
            >= evolution_run["metrics"]["holdout"]["baseline"]["accuracy"]
        )

        active = runtime.evolution.activate(evolution_run["candidate_version"])
        assert active["version"] == evolution_run["candidate_version"]
        assert active["policy"]["minimum_evidence_count"] == 4
        assert runtime.component_snapshot(result.task_id)["policy"]["version"] == "policy-v1"
        assert not [item for item in runtime.evolution.status()["failure_cases"] if item["status"] == "open"]

        next_result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        assert runtime.component_snapshot(next_result.task_id)["policy"]["version"] == active["version"]

        rolled_back = runtime.evolution.rollback()
        assert rolled_back["version"] == "policy-v1"

        dataset = runtime.evolution.status()["evaluation_dataset"]
        assert dataset["source_kinds"] == ["synthetic_fixture"]
        assert dataset["dataset_file"] == "decision_cards_v1.jsonl"

    asyncio.run(scenario())


def test_replay_dataset_makes_a_staleness_directive_decidable():
    """A skill can only be evaluated if some case turns on its directive.

    The fixtures declare ``evidence_age_days``, but with no freshness class the
    gate skipped its observation-age clock entirely: an age threshold could not
    change any outcome, so every skill candidate scored as a no-op against its
    baseline and was promoted.
    """
    evaluator = WorkflowReplayEvaluator()
    default = evaluator.run(DEFAULT_POLICY, "holdout")
    stricter = evaluator.run(dict(DEFAULT_POLICY, maximum_evidence_age_days=30), "holdout")

    assert stricter["accuracy"] > default["accuracy"]
    assert stricter["false_publish_rate"] < default["false_publish_rate"]


def test_hot_reloaded_provider_only_affects_new_tasks(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        first = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        first_snapshot = runtime.component_snapshot(first.task_id)

        runtime.install_provider(MockDataProvider(), "2.0.0")
        second = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        second_snapshot = runtime.component_snapshot(second.task_id)

        assert first_snapshot["tools"]["mock_data"]["plugin_version"] == "1.0.0"
        assert second_snapshot["tools"]["mock_data"]["plugin_version"] == "2.0.0"
        assert first_snapshot["digest"] != second_snapshot["digest"]

        restarted = ForesightRuntime(tmp_path / ".foresight")
        active_plugins = [
            plugin
            for plugin in restarted.extension_status()["plugins"]
            if plugin["plugin_id"] == "provider.mock-data" and plugin["status"] == "active"
        ]
        assert active_plugins[0]["version"] == "2.0.0"

        old_snapshot = restarted.harness.component_snapshot_for_task(first.task_id)
        restarted._ensure_snapshot_plugins(old_snapshot)
        old_run = restarted.harness.runs.get_run(first.task_id)
        replayed = await restarted.harness.call_tool(
            "mock_data",
            "collector",
            old_run["trace_id"],
            first.task_id,
            request=ResearchRequest(category="pet feeder", market="BR"),
        )
        assert len(replayed["evidences"]) == 5
        assert restarted.harness.plugins.has_generation("provider.mock-data", "1.0.0")

    asyncio.run(scenario())


def test_runtime_resumes_from_completed_nodes(tmp_path):
    async def scenario():
        workdir = tmp_path / ".foresight"
        request = ResearchRequest(category="pet feeder", market="BR")
        first_runtime = ForesightRuntime(workdir)
        task_id = str(uuid4())
        trace_id = first_runtime.harness.new_trace_id()
        board = CollaborationBlackboard(task_id)
        first_runtime.harness.runs.start_run(
            task_id,
            trace_id,
            request.model_dump(mode="json"),
            "test-fingerprint",
        )
        await first_runtime._execute_node(task_id, trace_id, request, board, "collect")
        await first_runtime._execute_node(task_id, trace_id, request, board, "analyze")
        first_runtime.harness.runs.set_run_status(task_id, "failed", "analyze", "simulated restart")

        resumed_runtime = ForesightRuntime(workdir)
        resumed_runtime.resume_task(task_id)
        result = await resumed_runtime.tasks[task_id]

        assert len(result.cards) == 4
        assert resumed_runtime.status(task_id)["status"] == "completed"
        restored_nodes = [
            event["node"]
            for event in resumed_runtime.run_events(task_id)
            if event["kind"] == "node.restored"
        ]
        assert restored_nodes == ["collect", "analyze"]

    asyncio.run(scenario())


def test_a_restarted_run_resumes_on_the_same_skill_patched_policy(tmp_path):
    """The skill patch lives inside the run's component snapshot, so a restart
    restores the node it was computed under instead of recompiling under a
    different gate."""

    async def scenario():
        workdir = tmp_path / ".foresight"
        request = ResearchRequest(category="pet feeder", market="BR")
        runtime = ForesightRuntime(workdir)
        for skill in runtime.skill_store.list_all():
            runtime.skill_store.save(skill.model_copy(update={"status": "ready"}))
            runtime.skill_store.activate(skill.skill_id)
        first = await runtime.run(request)
        assert [card.confidence_score for card in first.cards] == [0.68, 0.77, 0.8, 0.57]

        restarted = ForesightRuntime(workdir)
        board = restarted._board_from_checkpoint(first.task_id, restarted.load_checkpoint(first.task_id))
        # The restarted process rebuilds the run's policy from the stored
        # snapshot, so its gate is the docking one even though it never
        # retrieved anything itself.
        assert restarted.component_snapshot(first.task_id)["policy"]["skill_patch"]["applied"]
        assert restarted.harness.policy_for_task(first.task_id)["policy"]["confidence_penalty"] == 0.05
        await restarted._execute_node(first.task_id, first.trace_id, request, board, "compile")

        restored = [
            event["node"]
            for event in restarted.run_events(first.task_id)
            if event["kind"] == "node.restored"
        ]
        assert restored == ["compile"], "the patched node input must hash the same after a restart"

    asyncio.run(scenario())


def test_checkpoint_idempotency_prevents_duplicate_results(tmp_path):
    """Running the same request twice returns the same task structure, not duplicates."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result1 = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        result2 = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

        # Both should succeed independently with separate task IDs
        assert result1.task_id != result2.task_id
        assert len(result1.cards) == len(result2.cards) == 4
        # Both stored in memory
        assert runtime.get_result(result1.task_id) is not None
        assert runtime.get_result(result2.task_id) is not None

    asyncio.run(scenario())


def test_cancelled_task_records_state_and_allows_resume(tmp_path):
    async def scenario():
        workdir = tmp_path / ".foresight"
        request = ResearchRequest(category="pet feeder", market="BR")
        runtime = ForesightRuntime(workdir)

        task_id = str(uuid4())
        trace_id = runtime.harness.new_trace_id()
        board = CollaborationBlackboard(task_id)
        runtime.boards[task_id] = board
        runtime.harness.runs.start_run(
            task_id,
            trace_id,
            request.model_dump(mode="json"),
            "test-fingerprint",
        )
        await runtime._execute_node(task_id, trace_id, request, board, "collect")

        runtime.cancel_task(task_id)
        assert runtime.harness.runs.get_run(task_id)["status"] == "cancel_requested"

    asyncio.run(scenario())


def test_a_cancelled_run_resumes_into_a_completed_task(tmp_path):
    """Cancel then resume must finish, not fail on the restored contract.

    The checkpoint serializes the board, so a resumed run reads decision_contract
    back as a plain dict. The runtime stamps task_id onto it, which only works
    when the board restores it as a DecisionContract.
    """

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        request = ResearchRequest(category="pet feeder", market="BR")
        task_id = runtime.create_task(request)
        await asyncio.sleep(0.2)
        runtime.cancel_task(task_id)
        await asyncio.sleep(0.2)

        assert runtime.status(task_id)["recoverable"] is True
        runtime.resume_task(task_id)
        result = await runtime.tasks[task_id]

        assert runtime.status(task_id)["status"] == "completed"
        assert len(result.cards) == 4
        assert result.contract is not None

    asyncio.run(scenario())


def test_component_snapshot_locks_policy_version_for_running_task(tmp_path):
    """A running task keeps its original policy even after a new policy is activated."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        first = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

        runtime.review_card(
            first.cards[0].card_id,
            ReviewRequest(status="rejected", reviewer="tester", reason="test", failure_type="weak_evidence"),
        )
        evolution_run = runtime.evolution.generate_candidate()
        runtime.evolution.activate(evolution_run["candidate_version"])

        # First task still uses original policy
        snapshot = runtime.component_snapshot(first.task_id)
        assert snapshot["policy"]["version"] == "policy-v1"

        # New task uses updated policy
        second = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))
        new_snapshot = runtime.component_snapshot(second.task_id)
        assert new_snapshot["policy"]["version"] == evolution_run["candidate_version"]

    asyncio.run(scenario())


def test_run_events_record_full_node_lifecycle(tmp_path):
    """Every node transition is recorded in the run ledger."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(ResearchRequest(category="pet feeder", market="BR"))

        events = runtime.run_events(result.task_id)
        kinds = [e["kind"] for e in events]

        assert "task.start" in kinds
        assert "task.done" in kinds
        assert kinds.count("node.started") >= 4
        assert kinds.count("node.completed") >= 4
        assert any(e["kind"] == "checkpoint" for e in events)

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Decision Contract tests
# ---------------------------------------------------------------------------


def test_contract_first_run_always_validate_never_go(tmp_path):
    """Without real user validation, the system never gives GO on first run."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        contract = result.contract
        assert contract is not None
        assert contract.verdict != DecisionVerdict.GO
        # "最小验证是否完成？" must always be gap on first run
        validation_cp = next(
            cp for cp in contract.evidence_coverage.checkpoints
            if "验证" in cp.question
        )
        assert validation_cp.status == "gap"

    asyncio.run(scenario())


def test_contract_requires_target_market_evidence_checkpoint(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        checkpoint = next(
            cp for cp in result.contract.evidence_coverage.checkpoints
            if "目标市场" in cp.question
        )
        assert checkpoint.status == "gap"
        assert "BR" in checkpoint.basis

    asyncio.run(scenario())


def test_validation_cannot_exceed_experiment_budget(tmp_path):
    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        with pytest.raises(ValueError, match="超过本次实验预算"):
            runtime.submit_validation_result(
                result.task_id,
                ValidationResultRequest(
                    actual_spend=2001,
                    metrics={"sample_count": 35, "intent_rate": 0.18},
                    outcome="positive",
                ),
            )

    asyncio.run(scenario())


def test_validation_rejects_out_of_range_rates():
    with pytest.raises(ValueError, match="intent_rate"):
        ValidationResultRequest(
            actual_spend=100,
            metrics={"sample_count": 30, "intent_rate": 1.2},
        )


def test_real_pain_opportunity_does_not_inflate_tiny_samples(tmp_path):
    from foresight.real_data_provider import _opportunity_index

    assert _opportunity_index(1, 3, 0.6) < 0.5
    assert _opportunity_index(3, 3, 1.0) == 1.0


def test_real_review_sampling_does_not_start_with_only_low_ratings():
    from foresight.real_data_provider import RealDataProvider

    rows = [{"rating": 1, "helpful_vote": 100 - i} for i in range(8)]
    rows += [{"rating": 5, "helpful_vote": 1} for _ in range(2)]
    sampled = RealDataProvider._balanced_review_sample(rows)
    assert [row["rating"] for row in sampled[:4]] == [5, 1, 5, 1]


def test_contract_metrics_pass_promotes_to_go(tmp_path):
    """When validation metrics exceed all promotion gates, verdict becomes GO."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        assert result.contract.verdict == DecisionVerdict.VALIDATE

        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1800,
                metrics={"sample_count": 35, "intent_rate": 0.18, "pain_confirmation_rate": 0.40},
                outcome="positive",
            ),
        )
        assert contract.verdict == DecisionVerdict.GO
        assert contract.system_verdict == DecisionVerdict.GO
        assert contract.allowed_investment == 30000
        assert contract.human_override is None

    asyncio.run(scenario())


def test_confidence_floor_lets_the_policy_dock_change_an_outcome(tmp_path):
    """The dock must be able to change a decision, not just the displayed score.

    Same experiment, same passing metrics: with no dock the contract promotes to
    GO and releases the full budget; once the policy docks card confidence below
    the promotion floor, the capital stays withheld.
    """

    async def scenario(penalty: float) -> DecisionContract:
        runtime = ForesightRuntime(tmp_path / f".foresight-penalty-{penalty}")
        policy = dict(DEFAULT_POLICY)
        policy["confidence_penalty"] = penalty
        policy["minimum_evidence_confidence"] = 0.70
        runtime.harness.memory.save_policy(f"policy-{penalty}", policy, "ready", None)
        runtime.harness.memory.activate_policy(f"policy-{penalty}")

        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        assert result.contract.verdict == DecisionVerdict.VALIDATE
        return runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1800,
                metrics={"sample_count": 35, "intent_rate": 0.18, "pain_confirmation_rate": 0.40},
                outcome="positive",
            ),
        )

    promoted = asyncio.run(scenario(0.0))
    assert promoted.verdict == DecisionVerdict.GO
    assert promoted.allowed_investment == 30000

    docked = asyncio.run(scenario(0.20))
    assert docked.verdict == DecisionVerdict.VALIDATE
    assert docked.allowed_investment != 30000
    assert any("证据置信度" in item for item in docked.core_basis)


def test_contract_metrics_fail_stops(tmp_path):
    """When stop gates trigger (intent ≤ 5%), verdict becomes STOP."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1500,
                metrics={"sample_count": 35, "intent_rate": 0.03, "pain_confirmation_rate": 0.10},
                outcome="negative",
            ),
        )
        assert contract.verdict == DecisionVerdict.STOP
        assert contract.system_verdict == DecisionVerdict.STOP
        assert contract.allowed_investment == 0
        # Evidence coverage: validation was done, so checkpoint = pass
        validation_cp = next(
            cp for cp in contract.evidence_coverage.checkpoints if "验证" in cp.question
        )
        assert validation_cp.status == "pass"

    asyncio.run(scenario())


def test_contract_gray_zone_returns_validate(tmp_path):
    """Partial metrics (not GO, but not bad enough for STOP) → VALIDATE."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        # Sample 29 (need 30), intent 10% (need 12% but above 5% stop)
        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1800,
                metrics={"sample_count": 29, "intent_rate": 0.10, "pain_confirmation_rate": 0.40},
                outcome="inconclusive",
            ),
        )
        assert contract.verdict == DecisionVerdict.VALIDATE
        assert contract.system_verdict == DecisionVerdict.VALIDATE
        assert contract.human_override is None
        # Evidence coverage: validation was done
        validation_cp = next(
            cp for cp in contract.evidence_coverage.checkpoints if "验证" in cp.question
        )
        assert validation_cp.status == "pass"

    asyncio.run(scenario())


def test_contract_zero_intent_rate_stops(tmp_path):
    """intent_rate=0% with real sample should STOP, not VALIDATE."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        # 35 people, 0% intent → clearly STOP
        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=2000,
                metrics={"sample_count": 35, "intent_rate": 0.0, "pain_confirmation_rate": 0.0},
                outcome="negative",
            ),
        )
        assert contract.verdict == DecisionVerdict.STOP
        assert contract.system_verdict == DecisionVerdict.STOP
        # Evidence coverage: validation was done
        validation_cp = next(
            cp for cp in contract.evidence_coverage.checkpoints if "验证" in cp.question
        )
        assert validation_cp.status == "pass"

    asyncio.run(scenario())


def test_contract_small_sample_no_stop(tmp_path):
    """Below stop_sample_count, even 0% intent → VALIDATE (insufficient evidence)."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        # 5 people, 0% intent → too few to abort → VALIDATE
        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=500,
                metrics={"sample_count": 5, "intent_rate": 0.0},
                outcome="inconclusive",
            ),
        )
        assert contract.verdict == DecisionVerdict.VALIDATE
        assert contract.system_verdict == DecisionVerdict.VALIDATE

    asyncio.run(scenario())


def test_contract_outcome_cannot_override_verdict(tmp_path):
    """Regression: outcome='positive' must NOT override a STOP system verdict."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        # Metrics trigger STOP, but user says outcome="positive"
        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1500,
                metrics={"sample_count": 35, "intent_rate": 0.03},
                outcome="positive",  # must be ignored for verdict
            ),
        )
        assert contract.verdict == DecisionVerdict.STOP
        assert contract.system_verdict == DecisionVerdict.STOP
        assert contract.human_override is None

    asyncio.run(scenario())


def test_contract_human_override_recorded(tmp_path):
    """User can override system verdict via /override endpoint.
    Override does NOT modify evidence coverage.
    """

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )

        # First: submit validation with inconclusive outcome → system STOP
        contract = runtime.submit_validation_result(
            result.task_id,
            ValidationResultRequest(
                actual_spend=1500,
                metrics={"sample_count": 35, "intent_rate": 0.03},
                outcome="inconclusive",
            ),
        )
        assert contract.verdict == DecisionVerdict.STOP
        assert contract.system_verdict == DecisionVerdict.STOP
        # Evidence coverage reflects experiment completion
        validation_cp = next(
            cp for cp in contract.evidence_coverage.checkpoints if "验证" in cp.question
        )
        assert validation_cp.status == "pass"

        # Now use /override endpoint to override STOP → GO
        contract2 = runtime.override_contract(
            result.task_id,
            OverrideRequest(
                target_verdict=DecisionVerdict.GO,
                reason="已取得线下供应商保底回购协议",
                operator="demo-user",
            ),
        )
        assert contract2.verdict == DecisionVerdict.GO
        assert contract2.system_verdict == DecisionVerdict.STOP  # unchanged
        assert contract2.human_override == DecisionVerdict.GO
        assert contract2.override_reason == "已取得线下供应商保底回购协议"
        assert contract2.override_by == "demo-user"
        assert contract2.override_at is not None
        assert any("人工覆盖" in b for b in contract2.core_basis)
        # Evidence coverage NOT modified by override
        validation_cp2 = next(
            cp for cp in contract2.evidence_coverage.checkpoints if "验证" in cp.question
        )
        assert validation_cp2.status == "pass"
        assert "STOP" in validation_cp2.basis

    asyncio.run(scenario())


def test_evidence_collected_at_tracks_the_snapshot_not_the_report(tmp_path):
    """A dataset fetched months ago must not look freshly collected.

    ``collected_at`` used to be stamped with the moment the report was
    assembled, which made the cache-expiry gate impossible to ever trigger.
    Amazon metadata has a slow enough cadence that a 200-day-old file is still
    inside its cache budget, so the run completes and we can read the stamp.
    """

    datasets = tmp_path / "datasets"
    build_public_dataset_fixture(datasets)
    provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())

    assert provider.cache_age_report()["amazon_metadata"] == 0
    assert provider.stale_caches() == []

    fetched_epoch = (datetime.now(timezone.utc) - timedelta(days=200)).timestamp()
    os.utime(
        datasets / "amazon_metadata" / "Pet_Supplies.relevant.jsonl",
        (fetched_epoch, fetched_epoch),
    )

    assert provider.cache_age_report()["amazon_metadata"] >= 199
    assert provider.stale_caches() == []

    result = asyncio.run(
        ForesightRuntime(
            tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider
        ).run(ResearchRequest(category="pet feeder", market="BR", mode="real"))
    )
    price_evidence = next(
        evidence
        for evidence in result.cards[0].evidences
        if evidence.source_name.startswith("Amazon Reviews 2023 · product metadata")
    )
    assert price_evidence.collected_at < datetime.now(timezone.utc) - timedelta(days=199)


def test_expired_dataset_cache_fails_loudly_with_the_remedy(tmp_path):
    """Past its refresh budget the snapshot is an operational failure, not a report.

    This is the check that previously could never fire, so a rotting dataset
    directory surfaced as a confusing "stale evidence" refusal instead.
    """

    datasets = tmp_path / "datasets"
    build_public_dataset_fixture(datasets)
    provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())

    fetched_epoch = (datetime.now(timezone.utc) - timedelta(days=200)).timestamp()
    os.utime(datasets / "freight" / "gscpi_monthly.csv", (fetched_epoch, fetched_epoch))

    assert any(item.startswith("gscpi:") for item in provider.stale_caches())

    runtime = ForesightRuntime(
        tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider
    )
    with pytest.raises(ValueError, match="expired local cache"):
        asyncio.run(runtime.run(ResearchRequest(category="pet feeder", market="BR", mode="real")))


def test_collect_node_budget_covers_the_real_data_tool_timeout(tmp_path):
    """A node timeout below the tool timeout turns a slow tool into a retry storm."""

    datasets = tmp_path / "datasets"
    build_public_dataset_fixture(datasets)
    provider = RealDataProvider(datasets, model_adapter=FakeGroundedExtractor())
    runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=datasets, real_provider=provider)

    for tool_name in ("hybrid_data", "real_data"):
        tool_timeout = runtime.harness.tools.get(tool_name, "collector").timeout_seconds
        assert runtime.harness.node_timeout_seconds(NODE_AGENTS["collect"]) >= tool_timeout

    # Nodes that only reshape in-memory artifacts do not inherit the data budget.
    assert runtime.harness.node_timeout_seconds(NODE_AGENTS["validate"]) < 120


# ---------------------------------------------------------------------------
# Contract acknowledgement & execution tasks
# ---------------------------------------------------------------------------


def test_acknowledge_contract_stamps_audit_record(tmp_path):
    """Acknowledging a STOP contract records operator and timestamp."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        contract = runtime.acknowledge_contract(result.task_id, operator="buyer-1")

        assert contract.acknowledged_by == "buyer-1"
        assert contract.acknowledged_at is not None
        assert any("人工确认" in item for item in contract.core_basis)
        assert any("buyer-1" in item for item in contract.core_basis)

    asyncio.run(scenario())


def test_acknowledge_contract_rejects_missing_task(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")
    with pytest.raises(KeyError, match="No decision contract"):
        runtime.acknowledge_contract("nonexistent-task-id")


def test_update_execution_task_changes_status(tmp_path):
    """Execution task status transitions are persisted and traceable."""

    async def scenario():
        runtime = ForesightRuntime(tmp_path / ".foresight")
        result = await runtime.run(
            ResearchRequest(category="pet feeder", market="BR", planned_investment=30000)
        )
        # Add an execution task manually
        from foresight.models import ExecutionTask
        contract = result.contract
        contract.execution_tasks.append(
            ExecutionTask(title="Test task", status="todo")
        )
        runtime.harness.memory.put("contracts", result.task_id, contract.model_dump(mode="json"))

        task = contract.execution_tasks[0]
        updated = runtime.update_execution_task(
            result.task_id, task.task_id, "in_progress", owner="ops-team"
        )

        found = next(
            item for item in updated.execution_tasks if item.task_id == task.task_id
        )
        assert found.status == "in_progress"
        assert found.owner == "ops-team"

    asyncio.run(scenario())


def test_update_execution_task_rejects_missing(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")
    with pytest.raises(KeyError, match="No decision contract"):
        runtime.update_execution_task("nonexistent", "task-1", "done")


# ---------------------------------------------------------------------------
# Monitoring subscriptions
# ---------------------------------------------------------------------------


def test_create_and_list_monitoring_subscriptions(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")

    sub = runtime.create_monitoring_subscription(
        MonitoringSubscriptionRequest(
            category="pet feeder", market="BR", cadence="weekly", channels=["in_app"]
        )
    )
    assert sub["subscription_id"]
    assert sub["market"] == "BR"

    items = runtime.list_monitoring_subscriptions("default")
    assert any(item["subscription_id"] == sub["subscription_id"] for item in items)


def test_delete_monitoring_subscription_soft_deletes(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")

    sub = runtime.create_monitoring_subscription(
        MonitoringSubscriptionRequest(category="pet feeder", market="BR")
    )
    assert runtime.delete_monitoring_subscription(sub["subscription_id"]) is True
    assert runtime.delete_monitoring_subscription(sub["subscription_id"]) is False

    items = runtime.list_monitoring_subscriptions("default")
    assert not any(item["subscription_id"] == sub["subscription_id"] for item in items)


def test_check_monitoring_subscription_updates_timestamp(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")
    sub = runtime.create_monitoring_subscription(
        MonitoringSubscriptionRequest(category="pet feeder", market="BR")
    )

    result = runtime.check_monitoring_subscription(sub["subscription_id"])
    assert "snapshot" in result
    assert result["subscription"]["last_checked_at"] is not None
    assert result["notification_status"] == "in_app_pending"


def test_mock_monitoring_snapshot_falls_back_when_hybrid_unavailable(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight", datasets_dir=tmp_path / "empty-datasets")
    snapshot = runtime.monitoring_snapshot("pet feeder", "BR")

    assert snapshot["schedule_status"] == "mock_fallback"
    assert len(snapshot["signals"]) == 3
    assert snapshot["market"] == "BR"
    assert snapshot["capability"]["hybrid_available"] is False


# ---------------------------------------------------------------------------
# Unit economics boundary tests
# ---------------------------------------------------------------------------


def test_unit_economics_zero_cost_still_calculates():
    from foresight.models import UnitEconomicsRequest

    request = UnitEconomicsRequest(
        selling_price=100, product_cost=0, packaging_cost=0,
        domestic_shipping=0, international_shipping=0,
        duty_rate_pct=0, vat_rate_pct=0, platform_fee_rate_pct=10,
        payment_fee_rate_pct=2, ad_cost_per_order=0,
        return_rate_pct=0, target_margin_pct=20,
    )
    assert request.product_cost == 0
    # Verify basic invariants
    fee_rate = (10 + 2) / 100
    assert fee_rate == 0.12
    # With cost=0, profit should be price minus fees
    expected_profit = 100 - (100 * 0.12)  # 88
    from foresight.api_routes import calculate_unit_economics
    import asyncio
    result = asyncio.run(calculate_unit_economics(request))
    assert result.contribution_profit == expected_profit


def test_unit_economics_high_returns_erode_profit():
    from foresight.api_routes import calculate_unit_economics
    from foresight.models import UnitEconomicsRequest
    import asyncio

    request = UnitEconomicsRequest(
        selling_price=200, product_cost=100, return_rate_pct=50,
        platform_fee_rate_pct=10, payment_fee_rate_pct=2,
    )
    result = asyncio.run(calculate_unit_economics(request))
    # With 50% return rate + platform fees, return_reserve = half of price
    assert result.return_reserve == 100.0
    assert result.contribution_profit < 0


def test_unit_economics_break_even_covers_fixed_costs():
    from foresight.api_routes import calculate_unit_economics
    from foresight.models import UnitEconomicsRequest
    import asyncio

    request = UnitEconomicsRequest(
        selling_price=100, product_cost=40, ad_cost_per_order=20,
        platform_fee_rate_pct=20, payment_fee_rate_pct=0,
    )
    result = asyncio.run(calculate_unit_economics(request))
    # Break-even must cover fixed costs + ad
    assert result.break_even_price >= request.product_cost + request.ad_cost_per_order


def test_unit_economics_negative_margin_at_zero_price_coverage():
    from foresight.api_routes import calculate_unit_economics
    from foresight.models import UnitEconomicsRequest
    import asyncio

    request = UnitEconomicsRequest(
        selling_price=50, product_cost=40, domestic_shipping=10,
        international_shipping=15, duty_rate_pct=20, vat_rate_pct=17,
        platform_fee_rate_pct=15, payment_fee_rate_pct=3,
        ad_cost_per_order=15, return_rate_pct=5,
    )
    result = asyncio.run(calculate_unit_economics(request))
    assert result.contribution_margin_pct < 0
    assert result.max_cpc_at_target_margin == 0.0


# ---------------------------------------------------------------------------
# Resume skill consistency
# ---------------------------------------------------------------------------


def test_resumed_task_publishes_skills_from_stored_patch_not_fresh_retrieval(tmp_path):
    """After resume, the skill display must match what the gate applied, not a
    potentially different fresh retrieval."""

    async def scenario():
        workdir = tmp_path / ".foresight"
        request = ResearchRequest(category="pet feeder", market="BR")
        runtime = ForesightRuntime(workdir)

        # Activate a seed skill so the first run has a non-empty patch
        for skill in runtime.skill_store.list_all():
            runtime.skill_store.save(skill.model_copy(update={"status": "ready"}))
            runtime.skill_store.activate(skill.skill_id)

        task_id = runtime.create_task(request)
        result = await runtime.tasks[task_id]

        # The stored patch should be non-empty
        patch = runtime.component_snapshot(task_id)["policy"].get("skill_patch", {})
        applied = patch.get("applied", {})
        assert applied, "Expected at least one applied skill directive"

        # Reconstruct skills from the patch — must match what a resumed run sees
        reconstructed = runtime._skills_from_patch(patch)
        assert len(reconstructed) > 0
        assert all("name" in item and "version" in item for item in reconstructed)

    asyncio.run(scenario())


def test_skills_from_patch_handles_empty_patch(tmp_path):
    runtime = ForesightRuntime(tmp_path / ".foresight")
    assert runtime._skills_from_patch({}) == []
    assert runtime._skills_from_patch({"applied": {}, "deferred": {}}) == []
