import asyncio

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
