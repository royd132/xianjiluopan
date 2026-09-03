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
from .extensions import PluginManifest, ScopeContext, ToolDefinition
from .harness import stable_hash
from .harness_runtime import AgentHarness
from .skills import SkillBank, SkillStore, load_seed_skills
from .models import (
    DecisionCard,
    DecisionContract,
    DecisionVerdict,
    EvidenceItem,
    FeedbackRecord,
    PainPoint,
    ResearchRequest,
    ResearchResult,
    ReviewRequest,
    SupplySignal,
    ValidationResultRequest,
)
from .real_data_provider import ProviderUnavailableError, RealDataProvider


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
        self.skill_store = SkillStore(Path(workdir) / "skills.db")
        self.skills = SkillBank(self.skill_store)
        load_seed_skills(self.skill_store)
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

    def scenario_capabilities(self) -> list[dict[str, Any]]:
        return self.real_provider.scenario_capabilities()

    def has_event_stream(self, task_id: str) -> bool:
        """Return whether this process owns a live event stream for the task."""

        return task_id in self.boards

    def monitoring_snapshot(self, category: str, market: str) -> dict[str, Any]:
        if "hybrid" not in self.supported_modes:
            raise UnsupportedResearchModeError("Monitoring requires the public-data cache")
        try:
            return self.real_provider.monitoring_snapshot(category, market)
        except ProviderUnavailableError as exc:
            raise UnsupportedResearchModeError(str(exc)) from exc

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
        return handle

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
        return handle

    def _ensure_snapshot_plugins(self, snapshot) -> None:
        for plugin in snapshot.plugins:
            version = str(plugin["version"])
            plugin_id = plugin.get("plugin_id")
            if plugin_id == "provider.mock-data" and not self.harness.plugins.has_generation(
                plugin_id, version
            ):
                self.install_provider(
                    MockDataProvider(),
                    version,
                    make_active=False,
                    persist=False,
                )
            if plugin_id == "provider.real-data" and not self.harness.plugins.has_generation(
                plugin_id, version
            ):
                self.install_real_provider(
                    self.real_provider,
                    version,
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
            if request.mode != "real":
                return
            capability = self.real_provider.scenario_capability(request.category, request.market)
            if capability["real_available"]:
                return
            raise UnsupportedResearchModeError(
                f"Research mode 'real' is unavailable for {request.market.upper()} / "
                f"{capability['category_key']}. Missing: {', '.join(capability['blocking_reasons'])}."
            )
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
                ScopeContext(task_id=task_id),
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
                if node == "analyze":
                    retrieved = self.skills.retrieve_for_research(
                        request.category, request.market, request.mode
                    )
                    if retrieved:
                        await board.publish_artifact("retrieved_skills", retrieved, "skill-bank")
                        await board.publish_event(
                            RuntimeEvent(
                                EventType.SKILL_RETRIEVED,
                                task_id,
                                "skill-bank",
                                f"Retrieved {len(retrieved)} skills for decision compilation",
                                {"skills": [s["name"] for s in retrieved]},
                            )
                        )

            cards = board.read("decision_cards")
            contract = board.read("decision_contract")
            if contract:
                contract.task_id = task_id
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
                contract=contract,
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
        if review.status in {"rejected", "discussed"} and (review.reason or review.failure_type):
            self.skills.extract_candidate_from_feedback(
                feedback.model_dump(mode="json"), card
            )
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

    def submit_validation_result(
        self, task_id: str, result: ValidationResultRequest
    ) -> DecisionContract:
        """Accept actual validation data and re-evaluate the decision contract.

        Three-state verdict logic:
          - All promotion gates pass → GO
          - Any stop gate triggers → STOP
          - Gray zone (gates not met but no stop triggered) → VALIDATE

        Evidence coverage "最小验证是否完成？" reflects whether the experiment
        was actually conducted (has real metrics), NOT whether results passed.
        Human override does NOT modify evidence coverage.
        """
        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")

        contract = stored.contract
        if contract.verdict != DecisionVerdict.VALIDATE:
            raise ValueError(
                f"Validation results can only be submitted for VALIDATE contracts "
                f"(current: {contract.verdict.value})"
            )

        metrics = result.metrics
        criteria = contract.promotion_criteria

        # --- Promotion gates (GO threshold) ---
        promotion_passed: list[str] = []
        promotion_failed: list[str] = []

        sample = int(metrics.get("sample_count", 0))
        if sample >= criteria.min_sample_count:
            promotion_passed.append(f"样本量 {sample} ≥ {criteria.min_sample_count}")
        else:
            promotion_failed.append(f"样本量 {sample} < {criteria.min_sample_count}")

        intent = float(metrics.get("intent_rate", 0))
        if intent >= criteria.min_intent_rate:
            promotion_passed.append(f"意向率 {intent:.0%} ≥ {criteria.min_intent_rate:.0%}")
        else:
            promotion_failed.append(f"意向率 {intent:.0%} < {criteria.min_intent_rate:.0%}")

        if criteria.max_cpc is not None:
            cpc = float(metrics.get("cpc", 0))
            if cpc <= criteria.max_cpc:
                promotion_passed.append(f"CPC ¥{cpc:.2f} ≤ ¥{criteria.max_cpc:.2f}")
            else:
                promotion_failed.append(f"CPC ¥{cpc:.2f} > ¥{criteria.max_cpc:.2f}")

        if criteria.min_pain_confirmation_rate is not None:
            pain_rate = float(metrics.get("pain_confirmation_rate", 0))
            if pain_rate >= criteria.min_pain_confirmation_rate:
                promotion_passed.append(f"痛点确认率 {pain_rate:.0%} ≥ {criteria.min_pain_confirmation_rate:.0%}")
            else:
                promotion_failed.append(f"痛点确认率 {pain_rate:.0%} < {criteria.min_pain_confirmation_rate:.0%}")

        # --- Stop gates (abort threshold) ---
        stop_triggered: list[str] = []

        if intent > 0 and intent <= criteria.stop_intent_rate:
            stop_triggered.append(f"意向率 {intent:.0%} ≤ 否决线 {criteria.stop_intent_rate:.0%}")

        if sample > 0 and sample <= criteria.stop_sample_count and intent <= criteria.stop_intent_rate:
            stop_triggered.append(f"样本量 {sample} ≤ {criteria.stop_sample_count} 且意向率不达标")

        # --- Three-state verdict ---
        if not promotion_failed and promotion_passed:
            system_verdict = DecisionVerdict.GO
        elif stop_triggered:
            system_verdict = DecisionVerdict.STOP
        else:
            system_verdict = DecisionVerdict.VALIDATE

        # --- Human override ---
        human_override = None
        if result.outcome == "positive" and system_verdict != DecisionVerdict.GO:
            human_override = DecisionVerdict.GO
        elif result.outcome == "negative" and system_verdict != DecisionVerdict.STOP:
            human_override = DecisionVerdict.STOP

        new_verdict = human_override if human_override else system_verdict

        # --- Apply verdict ---
        if new_verdict == DecisionVerdict.GO:
            contract.allowed_investment = contract.planned_investment
        elif new_verdict == DecisionVerdict.STOP:
            contract.allowed_investment = 0

        contract.system_verdict = system_verdict
        contract.verdict = new_verdict
        contract.human_override = human_override
        if human_override:
            contract.override_reason = result.override_reason
            contract.override_by = result.override_by or "demo-user"
            contract.override_at = datetime.now(timezone.utc)
        contract.core_basis.append(
            f"验证结果：实际花费 ¥{result.actual_spend:.0f}"
        )
        if promotion_passed:
            contract.core_basis.append("晋级门通过：" + "；".join(promotion_passed))
        if promotion_failed:
            contract.core_basis.append("晋级门未通过：" + "；".join(promotion_failed))
        if stop_triggered:
            contract.core_basis.append("否决条件触发：" + "；".join(stop_triggered))
        if human_override:
            contract.core_basis.append(
                f"人工覆盖：系统判定={system_verdict.value}，"
                f"人工覆盖={human_override.value}"
                + (f"，理由={result.override_reason}" if result.override_reason else "")
            )

        # --- Evidence coverage: "验证完成" = experiment was conducted ---
        # This reflects whether real validation data exists, NOT whether it passed.
        # Override must NOT modify this.
        has_real_metrics = bool(metrics) and sample > 0
        for cp in contract.evidence_coverage.checkpoints:
            if "验证" in cp.question:
                cp.status = "pass" if has_real_metrics else "gap"
                cp.basis = (
                    f"验证实验已完成（{sample} 人），结果={system_verdict.value}，花费 ¥{result.actual_spend:.0f}"
                    if has_real_metrics
                    else "验证实验尚未执行"
                )
                break

        # Persist
        self.harness.memory.put("contracts", task_id, contract.model_dump(mode="json"))
        stored.contract = contract
        self.harness.memory.put("research_results", task_id, stored.model_dump(mode="json"))

        # Trace
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {
                "system_verdict": system_verdict.value,
                "verdict": new_verdict.value,
                "actual_spend": result.actual_spend,
                "human_override": human_override.value if human_override else None,
            }
            self.harness.trace.write(run["trace_id"], task_id, "validation.submitted", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "validation.submitted", payload, "validation")

        return contract

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        return self.harness.checkpoints.load(task_id)
