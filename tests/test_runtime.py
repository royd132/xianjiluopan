import asyncio
import csv
import json
from uuid import uuid4

import pytest

from foresight.events import CollaborationBlackboard
from foresight.data import MockDataProvider
from foresight.models import CardType, ResearchRequest, ReviewRequest
from foresight.policy import DEFAULT_POLICY, evaluate_decision_cards
from foresight.real_data_provider import RealDataProvider
from foresight.runtime import ForesightRuntime, UnsupportedResearchModeError


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
            writer.writerow(["2026-07-01", 5.0])
            writer.writerow(["2026-08-20", 5.1])
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
        assert fx.observed_at.date().isoformat() == "2026-08-20"
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
    assert signals["fx"]["observed_at"] == "2026-08-20"
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
