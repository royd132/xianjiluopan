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
from .evolution import EvolutionEngine, FeedbackFlywheel
from .extensions import PluginManifest, ScopeContext
from .harness import AgentHarness, ToolDefinition, stable_hash
from .models import (
    DecisionCard,
    EvidenceItem,
    FeedbackRecord,
    PainPoint,
    ResearchRequest,
    ResearchResult,
    ReviewRequest,
    SupplySignal,
)
from .real_data_provider import RealDataProvider


class UnsupportedResearchModeError(ValueError):
    """Raised when a request asks for a data mode with no installed provider."""


class ForesightRuntime:
    """Event-driven coordinator backed by a resumable node runtime."""

    workflow_version = "foresight-workflow-v3"

    def __init__(
        self,
        workdir: Path | str = ".foresight",
        datasets_dir: Path | str = "datasets",
        real_provider: RealDataProvider | None = None,
    ) -> None:
        self.harness = AgentHarness(workdir)
        self.flywheel = FeedbackFlywheel(self.harness.memory)
        self.evolution = EvolutionEngine(self.harness.memory)
        self.provider = MockDataProvider()
        self.real_provider = real_provider or RealDataProvider(datasets_dir)
        self.boards: dict[str, CollaborationBlackboard] = {}
        self.tasks: dict[str, asyncio.Task[ResearchResult]] = {}
        self.results: dict[str, ResearchResult] = {}
        self.card_index: dict[str, tuple[str, dict[str, Any]]] = {}
        provider_state = self.harness.memory.get(
            "runtime_plugins", "global:provider.mock-data"
        ) or {"version": "1.0.0"}
        self.install_provider(
            self.provider,
            str(provider_state.get("version", "1.0.0")),
            persist=False,
        )
        real_provider_state = self.harness.memory.get(
            "runtime_plugins", "global:provider.real-data"
        ) or {"version": self.real_provider.provider_version}
        self.install_real_provider(
            self.real_provider,
            str(real_provider_state.get("version", self.real_provider.provider_version)),
            persist=False,
        )

    @property
    def supported_modes(self) -> frozenset[str]:
        status = self.real_provider.data_status()
        modes = {"mock"}
        if status["hybrid_ready"]:
            modes.add("hybrid")
        if status["real_ready"]:
            modes.add("real")
        return frozenset(modes)

    def install_provider(
        self,
        provider: MockDataProvider,
        version: str,
        scope_key: str = "global",
        make_active: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        manifest = PluginManifest(
            plugin_id="provider.mock-data",
            version=version,
            kind="provider",
            description="Deterministic offline market data provider",
            capabilities=("tool:mock_data",),
            permissions=("offline-dataset:read",),
        )

        def install(context) -> None:
            context.register_tool(
                ToolDefinition(
                    name="mock_data",
                    handler=provider.collect,
                    allowed_agents=frozenset({"collector"}),
                    timeout_seconds=20,
                    description="Collect normalized market evidence for one research request",
                )
            )

        handle = self.harness.plugins.install(
            manifest,
            install,
            scope_key=scope_key,
            health_check=lambda _context: callable(provider.collect),
            make_active=make_active,
        )
        if make_active:
            self.provider = provider
            if persist:
                self.harness.memory.put(
                    "runtime_plugins",
                    f"{scope_key}:{manifest.plugin_id}",
                    {"version": version, "scope_key": scope_key, "manifest": manifest.as_dict()},
                )
        return handle.as_dict()

    def install_real_provider(
        self,
        provider: RealDataProvider,
        version: str,
        scope_key: str = "global",
        make_active: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        manifest = PluginManifest(
            plugin_id="provider.real-data",
            version=version,
            kind="provider",
            description="Public market datasets plus grounded Qwen review extraction",
            capabilities=("tool:hybrid_data", "tool:real_data"),
            permissions=("local-dataset:read", "model-api:call"),
        )

        def install(context) -> None:
            context.register_tool(
                ToolDefinition(
                    name="hybrid_data",
                    handler=provider.collect_hybrid,
                    allowed_agents=frozenset({"collector"}),
                    timeout_seconds=120,
                    description="Collect public evidence with explicitly marked fallbacks",
                )
            )
            context.register_tool(
                ToolDefinition(
                    name="real_data",
                    handler=provider.collect_real,
                    allowed_agents=frozenset({"collector"}),
                    timeout_seconds=120,
                    description="Collect public evidence and require grounded Qwen extraction",
                )
            )

        handle = self.harness.plugins.install(
            manifest,
            install,
            scope_key=scope_key,
            health_check=lambda _context: callable(provider.collect_real) and callable(provider.collect_hybrid),
            make_active=make_active,
        )
        if make_active:
            self.real_provider = provider
            if persist:
                self.harness.memory.put(
                    "runtime_plugins",
                    f"{scope_key}:{manifest.plugin_id}",
                    {"version": version, "scope_key": scope_key, "manifest": manifest.as_dict()},
                )
        return handle.as_dict()

    def rollback_provider(self, scope_key: str = "global") -> dict[str, Any]:
        handle = self.harness.plugins.rollback("provider.mock-data", scope_key)
        self.harness.memory.put(
            "runtime_plugins",
            f"{scope_key}:provider.mock-data",
            {
                "version": handle.manifest.version,
                "scope_key": scope_key,
                "manifest": handle.manifest.as_dict(),
            },
        )
        return handle.as_dict()

    def _ensure_snapshot_plugins(self, snapshot) -> None:
        for plugin in snapshot.plugins:
            version = str(plugin["version"])
            scope_key = str(plugin.get("scope_key", "global"))
            plugin_id = plugin.get("plugin_id")
            if plugin_id == "provider.mock-data" and not self.harness.plugins.has_generation(
                plugin_id, version, scope_key
            ):
                self.install_provider(
                    MockDataProvider(),
                    version,
                    scope_key=scope_key,
                    make_active=False,
                    persist=False,
                )
            if plugin_id == "provider.real-data" and not self.harness.plugins.has_generation(
                plugin_id, version, scope_key
            ):
                self.install_real_provider(
                    self.real_provider,
                    version,
                    scope_key=scope_key,
                    make_active=False,
                    persist=False,
                )

    def create_task(self, request: ResearchRequest) -> str:
        self._validate_request_mode(request)
        task_id = str(uuid4())
        board = CollaborationBlackboard(task_id)
        self.boards[task_id] = board
        self.tasks[task_id] = asyncio.create_task(self._execute(task_id, request, board))
        return task_id

    def resume_task(self, task_id: str) -> str:
        active_task = self.tasks.get(task_id)
        if active_task and not active_task.done():
            raise ValueError("Task is already running")
        run = self.harness.runs.get_run(task_id)
        if not run:
            raise KeyError(task_id)
        if run["status"] == "completed":
            return task_id
        checkpoint = self.load_checkpoint(task_id)
        if not checkpoint:
            raise ValueError("No checkpoint is available for this task")
        request = ResearchRequest.model_validate(run["request"])
        self._validate_request_mode(request)
        board = self._board_from_checkpoint(task_id, checkpoint)
        self.boards[task_id] = board
        self.tasks[task_id] = asyncio.create_task(
            self._execute(task_id, request, board, trace_id=run["trace_id"], resumed=True)
        )
        return task_id

    def cancel_task(self, task_id: str) -> None:
        self.harness.runs.request_cancel(task_id)
        task = self.tasks.get(task_id)
        if task and not task.done():
            task.cancel()

    async def run(self, request: ResearchRequest) -> ResearchResult:
        task_id = self.create_task(request)
        return await self.tasks[task_id]

    def _validate_request_mode(self, request: ResearchRequest) -> None:
        if request.mode in self.supported_modes:
            return
        supported = ", ".join(sorted(self.supported_modes))
        raise UnsupportedResearchModeError(
            f"Research mode '{request.mode}' is not available. "
            f"Installed providers support: {supported}."
        )

    def _serialize_snapshot(self, board: CollaborationBlackboard) -> dict[str, Any]:
        def serialize(value: Any) -> Any:
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json")
            if isinstance(value, dict):
                return {key: serialize(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [serialize(item) for item in value]
            return value

        return serialize(board.snapshot())

    def _board_from_checkpoint(self, task_id: str, checkpoint: dict[str, Any]) -> CollaborationBlackboard:
        board = CollaborationBlackboard(task_id)
        snapshot = dict(checkpoint.get("payload", {}))
        raw = snapshot.get("raw_market_data")
        if raw and isinstance(raw.get("evidences"), list):
            raw["evidences"] = [EvidenceItem.model_validate(item) for item in raw["evidences"]]
        if isinstance(snapshot.get("evidences"), list):
            snapshot["evidences"] = [EvidenceItem.model_validate(item) for item in snapshot["evidences"]]
        if isinstance(snapshot.get("pain_points"), list):
            snapshot["pain_points"] = [PainPoint.model_validate(item) for item in snapshot["pain_points"]]
        if isinstance(snapshot.get("supply_signals"), list):
            snapshot["supply_signals"] = [SupplySignal.model_validate(item) for item in snapshot["supply_signals"]]
        for key in ("decision_cards_draft", "decision_cards"):
            if isinstance(snapshot.get(key), list):
                snapshot[key] = [DecisionCard.model_validate(item) for item in snapshot[key]]
        board.artifacts = snapshot
        return board

    async def _checkpoint(
        self,
        task_id: str,
        stage: str,
        board: CollaborationBlackboard,
        trace_id: str,
    ) -> dict[str, Any]:
        serializable = self._serialize_snapshot(board)
        path = self.harness.checkpoints.save(task_id, stage, serializable)
        payload = {"stage": stage, "path": str(path), "snapshot_hash": stable_hash(serializable)}
        self.harness.trace.write(trace_id, task_id, "checkpoint", payload)
        self.harness.runs.record_event(task_id, trace_id, "checkpoint", payload, stage)
        await board.publish_event(
            RuntimeEvent(
                EventType.CHECKPOINT_SAVED,
                task_id,
                "harness",
                f"Checkpoint saved: {stage}",
                {"stage": stage},
            )
        )
        return serializable

    async def _execute_node(
        self,
        task_id: str,
        trace_id: str,
        request: ResearchRequest,
        board: CollaborationBlackboard,
        node: str,
    ) -> dict[str, Any]:
        async def operation() -> dict[str, Any]:
            if node == "collect":
                await CollectorAgent().execute(request, board, self.harness, trace_id)
                return await self._checkpoint(task_id, "collected", board, trace_id)
            if node == "analyze":
                await run_parallel(
                    [MultilingualReviewAgent(), MarketAnalysisAgent(), SupplyChainAgent()],
                    request,
                    board,
                    self.harness,
                    trace_id,
                )
                return await self._checkpoint(task_id, "analyzed", board, trace_id)
            if node == "compile":
                await DecisionCompilerAgent().execute(request, board, self.harness, trace_id)
                return await self._checkpoint(task_id, "compiled", board, trace_id)
            if node == "validate":
                await SafetyEvaluationAgent().execute(request, board, self.harness, trace_id)
                return await self._checkpoint(task_id, "validated", board, trace_id)
            raise KeyError(node)

        snapshot = self.harness.component_snapshot_for_task(task_id)
        return await self.harness.run_node(
            task_id=task_id,
            trace_id=trace_id,
            node=node,
            input_value={
                "request": request.model_dump(mode="json"),
                "workflow_version": self.workflow_version,
                "policy_version": snapshot.policy.get("version", "embedded-default"),
                "component_snapshot": snapshot.digest,
                "node": node,
            },
            operation=operation,
        )

    async def _execute(
        self,
        task_id: str,
        request: ResearchRequest,
        board: CollaborationBlackboard,
        trace_id: str | None = None,
        resumed: bool = False,
    ) -> ResearchResult:
        with self.harness.storage_scope():
            return await self._execute_in_storage(task_id, request, board, trace_id, resumed)

    async def _execute_in_storage(
        self,
        task_id: str,
        request: ResearchRequest,
        board: CollaborationBlackboard,
        trace_id: str | None = None,
        resumed: bool = False,
    ) -> ResearchResult:
        self._validate_request_mode(request)
        started_at = datetime.now(timezone.utc)
        trace_id = trace_id or self.harness.new_trace_id()
        existing_run = self.harness.runs.get_run(task_id)
        if existing_run and existing_run.get("component_snapshot"):
            component_snapshot = self.harness.component_snapshot_for_task(task_id)
            self._ensure_snapshot_plugins(component_snapshot)
        else:
            active_policy = self.evolution.active_policy()
            component_snapshot = self.harness.create_component_snapshot(
                ScopeContext(
                    tenant_id=request.workspace_id,
                    preset_id=request.market,
                    task_id=task_id,
                ),
                {"version": active_policy["version"], "policy": active_policy["policy"]},
            )
        fingerprint = stable_hash(
            {
                "workflow": self.workflow_version,
                "harness": self.harness.runtime_version,
                "request": request.model_dump(mode="json"),
                "component_snapshot": component_snapshot.digest,
            }
        )
        self.harness.runs.start_run(
            task_id,
            trace_id,
            request.model_dump(mode="json"),
            fingerprint,
            component_snapshot.as_dict(),
        )
        event_kind = "task.resumed" if resumed else "task.start"
        event_message = "Research task resumed from checkpoint" if resumed else "Research task started"
        await board.publish_event(
            RuntimeEvent(EventType.TASK_STARTED, task_id, "coordinator", event_message, request.model_dump())
        )
        start_payload = {
            **request.model_dump(mode="json"),
            "component_snapshot": component_snapshot.digest,
            "plugins": [plugin["plugin_id"] + "@" + plugin["version"] for plugin in component_snapshot.plugins],
            "policy_version": component_snapshot.policy.get("version"),
        }
        self.harness.trace.write(trace_id, task_id, event_kind, start_payload)
        self.harness.runs.record_event(task_id, trace_id, event_kind, start_payload)
        try:
            for node in ("collect", "analyze", "compile", "validate"):
                await self._execute_node(task_id, trace_id, request, board, node)

            cards = board.read("decision_cards")
            result = ResearchResult(
                task_id=task_id,
                request=request,
                cards=cards,
                pain_points=board.read("pain_points"),
                supply_signals=board.read("supply_signals"),
                evidence_count=len(board.read("evidences", [])),
                agents_completed=[
                    "collector",
                    "review-analyzer",
                    "market-analyzer",
                    "supply-chain-analyzer",
                    "decision-compiler",
                    "safety-evaluator",
                ],
                mode=request.mode,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                trace_id=trace_id,
            )
            self.results[task_id] = result
            self.harness.memory.put("research_results", task_id, result.model_dump(mode="json"))
            for card in result.cards:
                card_payload = card.model_dump(mode="json")
                self.card_index[card.card_id] = (task_id, card_payload)
                self.harness.memory.put("cards", card.card_id, {"task_id": task_id, "card": card_payload})
            self.harness.runs.set_run_status(task_id, "completed", "validate")
            self.harness.trace.write(trace_id, task_id, "task.done", {"cards": len(cards)})
            self.harness.runs.record_event(task_id, trace_id, "task.done", {"cards": len(cards)})
            await board.publish_event(
                RuntimeEvent(
                    EventType.TASK_COMPLETED,
                    task_id,
                    "coordinator",
                    "Four decision cards are ready",
                    {"cards": len(cards), "trace_id": trace_id},
                )
            )
            return result
        except asyncio.CancelledError:
            self.harness.runs.set_run_status(task_id, "cancelled", error="cancelled")
            self.harness.trace.write(trace_id, task_id, "task.cancelled", {})
            self.harness.runs.record_event(task_id, trace_id, "task.cancelled", {})
            await board.publish_event(
                RuntimeEvent(EventType.TASK_CANCELLED, task_id, "coordinator", "Research task cancelled")
            )
            raise
        except Exception as exc:
            self.harness.runs.set_run_status(task_id, "failed", error=str(exc))
            self.harness.trace.write(trace_id, task_id, "task.error", {"error": str(exc)})
            self.harness.runs.record_event(task_id, trace_id, "task.error", {"error": str(exc)})
            await board.publish_event(RuntimeEvent(EventType.TASK_FAILED, task_id, "coordinator", str(exc)))
            raise

    def status(self, task_id: str) -> dict[str, Any]:
        run = self.harness.runs.get_run(task_id)
        if not run:
            raise KeyError(task_id)
        task = self.tasks.get(task_id)
        status = run["status"]
        if task and task.done() and task.cancelled():
            status = "cancelled"
        checkpoint = self.load_checkpoint(task_id)
        board = self.boards.get(task_id)
        return {
            "task_id": task_id,
            "status": status,
            "current_node": run.get("current_node"),
            "trace_id": run["trace_id"],
            "event_count": len(board.events) if board else len(self.harness.runs.list_events(task_id)),
            "artifacts": sorted(board.artifacts) if board else sorted((checkpoint or {}).get("payload", {})),
            "recoverable": status in {"failed", "cancelled", "cancel_requested"} and checkpoint is not None,
            "component_snapshot": run.get("component_snapshot", {}).get("digest"),
            "policy_version": run.get("component_snapshot", {}).get("policy", {}).get("version"),
        }

    def get_result(self, task_id: str) -> ResearchResult | None:
        result = self.results.get(task_id)
        if result:
            return result
        stored = self.harness.memory.get("research_results", task_id)
        if not stored:
            return None
        result = ResearchResult.model_validate(stored)
        self.results[task_id] = result
        return result

    async def events(self, task_id: str) -> AsyncIterator[RuntimeEvent]:
        board = self.boards.get(task_id)
        if not board:
            raise KeyError(task_id)
        async for event in board.subscribe():
            yield event

    def run_events(self, task_id: str) -> list[dict[str, Any]]:
        if not self.harness.runs.get_run(task_id):
            raise KeyError(task_id)
        return self.harness.runs.list_events(task_id)

    def component_snapshot(self, task_id: str) -> dict[str, Any]:
        return self.harness.component_snapshot_for_task(task_id).as_dict()

    def extension_status(self) -> dict[str, Any]:
        return {
            "runtime_version": self.harness.runtime_version,
            "workflow_version": self.workflow_version,
            "supported_modes": sorted(self.supported_modes),
            "real_data": self.real_provider.data_status(),
            "plugins": self.harness.plugins.list(),
        }

    def review_card(self, card_id: str, review: ReviewRequest) -> FeedbackRecord:
        indexed = self.card_index.get(card_id)
        if not indexed:
            stored = self.harness.memory.get("cards", card_id)
            if not stored:
                raise KeyError(card_id)
            indexed = (stored["task_id"], stored["card"])
            self.card_index[card_id] = indexed
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
            failure_type=review.failure_type,
        )
        failure = self.flywheel.record(feedback, card)
        self.harness.memory.put("reviewed_cards", card_id, card)
        self.harness.memory.put("cards", card_id, {"task_id": task_id, "card": card})
        result = self.get_result(task_id)
        if result:
            result.cards = [DecisionCard.model_validate(card) if item.card_id == card_id else item for item in result.cards]
            self.harness.memory.put("research_results", task_id, result.model_dump(mode="json"))
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {
                "feedback_id": feedback.feedback_id,
                "card_id": card_id,
                "status": review.status,
                "failure_id": failure["failure_id"] if failure else None,
            }
            self.harness.trace.write(run["trace_id"], task_id, "feedback.recorded", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "feedback.recorded", payload, "human-review")
        return feedback

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        return self.harness.checkpoints.load(task_id)
