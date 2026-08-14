import asyncio
from uuid import uuid4

from foresight.events import CollaborationBlackboard
from foresight.data import MockDataProvider
from foresight.models import CardType, ResearchRequest, ReviewRequest
from foresight.runtime import ForesightRuntime


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
        assert evolution_run["metrics"]["validation"]["candidate"]["execution_path"][1] == "production safety gate"
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
