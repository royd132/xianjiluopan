from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from .agents import (
    CollectorAgent,
    DecisionCompilerAgent,
    MarketAnalysisAgent,
    MultilingualReviewAgent,
    SafetyEvaluationAgent,
    SupplyChainAgent,
    run_parallel,
)
from .data import MockDataProvider
from .events import CollaborationBlackboard, EventType, RuntimeEvent
from .evolution import FeedbackFlywheel
from .harness import AgentHarness
from .models import FeedbackRecord, ResearchRequest, ResearchResult, ReviewRequest


class ForesightRuntime:
    """Event-driven multi-agent coordinator for a complete research task."""

    def __init__(self, workdir: Path | str = ".foresight") -> None:
        self.harness = AgentHarness(workdir)
        self.flywheel = FeedbackFlywheel(self.harness.memory)
        self.provider = MockDataProvider()
        self.boards: dict[str, CollaborationBlackboard] = {}
        self.tasks: dict[str, asyncio.Task[ResearchResult]] = {}
        self.results: dict[str, ResearchResult] = {}
        self.card_index: dict[str, tuple[str, dict[str, Any]]] = {}

    def create_task(self, request: ResearchRequest) -> str:
        task_id = str(uuid4())
        board = CollaborationBlackboard(task_id)
        self.boards[task_id] = board
        self.tasks[task_id] = asyncio.create_task(self._execute(task_id, request, board))
        return task_id

    async def run(self, request: ResearchRequest) -> ResearchResult:
        task_id = self.create_task(request)
        return await self.tasks[task_id]

    async def _checkpoint(self, task_id: str, stage: str, board: CollaborationBlackboard, trace_id: str) -> None:
        snapshot = board.snapshot()
        serializable = {
            key: [item.model_dump(mode="json") for item in value] if isinstance(value, list) and value and hasattr(value[0], "model_dump")
            else value.model_dump(mode="json") if hasattr(value, "model_dump")
            else value
            for key, value in snapshot.items()
        }
        path = self.harness.checkpoints.save(task_id, stage, serializable)
        self.harness.trace.write(trace_id, task_id, "checkpoint", {"stage": stage, "path": str(path)})
        await board.publish_event(RuntimeEvent(EventType.CHECKPOINT_SAVED, task_id, "harness", f"Checkpoint saved: {stage}", {"stage": stage}))

    async def _execute(self, task_id: str, request: ResearchRequest, board: CollaborationBlackboard) -> ResearchResult:
        started_at = datetime.now(timezone.utc)
        trace_id = self.harness.new_trace_id()
        await board.publish_event(RuntimeEvent(EventType.TASK_STARTED, task_id, "coordinator", "Research task started", request.model_dump()))
        self.harness.trace.write(trace_id, task_id, "task.start", request.model_dump())
        try:
            collector = CollectorAgent(self.provider)
            await collector.execute(request, board, self.harness, trace_id)
            await self._checkpoint(task_id, "collected", board, trace_id)

            await run_parallel(
                [MultilingualReviewAgent(), MarketAnalysisAgent(), SupplyChainAgent()],
                request,
                board,
                self.harness,
                trace_id,
            )
            await self._checkpoint(task_id, "analyzed", board, trace_id)

            await DecisionCompilerAgent().execute(request, board, self.harness, trace_id)
            await SafetyEvaluationAgent().execute(request, board, self.harness, trace_id)
            await self._checkpoint(task_id, "validated", board, trace_id)

            cards = board.read("decision_cards")
            result = ResearchResult(
                task_id=task_id,
                request=request,
                cards=cards,
                pain_points=board.read("pain_points"),
                supply_signals=board.read("supply_signals"),
                evidence_count=len(board.read("evidences", [])),
                agents_completed=["collector", "review-analyzer", "market-analyzer", "supply-chain-analyzer", "decision-compiler", "safety-evaluator"],
                mode=request.mode,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                trace_id=trace_id,
            )
            self.results[task_id] = result
            self.harness.memory.put("research_results", task_id, result.model_dump(mode="json"))
            for card in result.cards:
                self.card_index[card.card_id] = (task_id, card.model_dump(mode="json"))
            self.harness.trace.write(trace_id, task_id, "task.done", {"cards": len(cards)})
            await board.publish_event(RuntimeEvent(EventType.TASK_COMPLETED, task_id, "coordinator", "Four decision cards are ready", {"cards": len(cards), "trace_id": trace_id}))
            return result
        except Exception as exc:
            self.harness.trace.write(trace_id, task_id, "task.error", {"error": str(exc)})
            await board.publish_event(RuntimeEvent(EventType.TASK_FAILED, task_id, "coordinator", str(exc)))
            raise

    def status(self, task_id: str) -> dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "status": "failed" if task.done() and task.exception() else "completed" if task.done() else "running",
            "event_count": len(self.boards[task_id].events),
            "artifacts": sorted(self.boards[task_id].artifacts),
        }

    def get_result(self, task_id: str) -> ResearchResult | None:
        return self.results.get(task_id)

    async def events(self, task_id: str) -> AsyncIterator[RuntimeEvent]:
        board = self.boards.get(task_id)
        if not board:
            raise KeyError(task_id)
        async for event in board.subscribe():
            yield event

    def review_card(self, card_id: str, review: ReviewRequest) -> FeedbackRecord:
        indexed = self.card_index.get(card_id)
        if not indexed:
            raise KeyError(card_id)
        task_id, card = indexed
        card["human_review_status"] = review.status
        card["human_reviewer"] = review.reviewer
        card["human_reviewed_at"] = datetime.now(timezone.utc).isoformat()
        feedback = FeedbackRecord(
            card_id=card_id,
            task_id=task_id,
            feedback_type=review.status,
            user_id=review.reviewer,
            reason=review.reason,
        )
        self.flywheel.record(feedback, card)
        self.harness.memory.put("reviewed_cards", card_id, card)
        return feedback

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        return self.harness.checkpoints.load(task_id)
