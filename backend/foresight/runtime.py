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
from .data import MARKET_PROFILES, MockDataProvider
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
    MonitoringSubscriptionRequest,
    FeedbackRecord,
    OverrideRequest,
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


# Which agents a node runs, so the node's timeout can be sized against the tools
# those agents are allowed to call. Keep in step with _execute_node.
NODE_AGENTS: dict[str, tuple[str, ...]] = {
    "collect": ("collector",),
    "analyze": ("review-analyzer", "market-analyzer", "supply-chain-analyzer"),
    "compile": ("decision-compiler",),
    "validate": ("safety-evaluator",),
}


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
            return self._mock_monitoring_snapshot(category, market)
        try:
            return self.real_provider.monitoring_snapshot(category, market)
        except ProviderUnavailableError as exc:
            raise UnsupportedResearchModeError(str(exc)) from exc

    def _mock_monitoring_snapshot(self, category: str, market: str) -> dict[str, Any]:
        from .data import resolve_category, resolve_market

        market_profile = resolve_market(market)
        category_profile = resolve_category(category)
        now = datetime.now(timezone.utc)
        return {
            "category": category,
            "category_key": str(category_profile["key"]),
            "market": market.upper(),
            "generated_at": now.isoformat(),
            "schedule_status": "mock_fallback",
            "signals": [
                {
                    "key": "fx",
                    "label": market_profile["fx_label"],
                    "observed_at": now.date().isoformat(),
                    "value": market_profile["fx_value"],
                    "change_pct": 0.8,
                    "threshold": "abs(30d) >= 5%",
                    "triggered": False,
                },
                {
                    "key": "trade",
                    "label": f'{market.upper()} HS{category_profile["hs_code"]} 进口额',
                    "observed_at": str(now.year),
                    "value": float(market_profile["import_growth"]),
                    "change_pct": market_profile["import_growth"],
                    "threshold": "abs(YoY) >= 20%",
                    "triggered": market_profile["import_growth"] >= 20,
                },
                {
                    "key": "gscpi",
                    "label": "全球供应链压力指数 GSCPI",
                    "observed_at": now.date().isoformat(),
                    "value": 0.0,
                    "change_pct": 0.0,
                    "threshold": "指数 >= 1 或月变动 >= 15%",
                    "triggered": False,
                },
            ],
            "trigger_count": 1 if market_profile["import_growth"] >= 20 else 0,
            "capability": self.real_provider.scenario_capability(category, market),
        }

    def list_monitoring_subscriptions(self, workspace_id: str = "default") -> list[dict[str, Any]]:
        return self.harness.runs.list_monitoring_subscriptions(workspace_id)

    def create_monitoring_subscription(self, request: MonitoringSubscriptionRequest) -> dict[str, Any]:
        if request.market.upper() not in MARKET_PROFILES:
            raise ValueError(f"Unsupported target market: {request.market.upper()}")
        subscription = request.model_dump(mode="json")
        subscription.update({"subscription_id": str(uuid4()), "market": request.market.upper(), "created_at": datetime.now(timezone.utc).isoformat()})
        return self.harness.runs.create_monitoring_subscription(subscription)

    def check_monitoring_subscription(self, subscription_id: str) -> dict[str, Any]:
        subscriptions = self.harness.runs.list_monitoring_subscriptions(None)
        subscription = next((item for item in subscriptions if item["subscription_id"] == subscription_id), None)
        if subscription is None:
            raise KeyError(subscription_id)
        snapshot = self.monitoring_snapshot(subscription["category"], subscription["market"])
        updated = self.harness.runs.touch_monitoring_subscription(
            subscription_id, datetime.now(timezone.utc).isoformat(), int(snapshot.get("trigger_count", 0))
        )
        return {"subscription": updated, "snapshot": snapshot, "notification_status": "in_app_pending"}

    def delete_monitoring_subscription(self, subscription_id: str) -> bool:
        return self.harness.runs.delete_monitoring_subscription(subscription_id)

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
        if request.market.upper() not in MARKET_PROFILES:
            raise UnsupportedResearchModeError(
                f"Unsupported target market: {request.market.upper()}. "
                f"Choose one of: {', '.join(sorted(MARKET_PROFILES))}."
            )
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
        # The contract is read back by _execute_in_storage, which stamps task_id
        # onto it. Left as a dict it would blow up there and turn every resume of
        # a run that already compiled into a failed task.
        if isinstance(snapshot.get("decision_contract"), dict):
            snapshot["decision_contract"] = DecisionContract.model_validate(snapshot["decision_contract"])
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
            agents=NODE_AGENTS.get(node, ()),
            input_value={
                "request": request.model_dump(mode="json"),
                "workflow_version": self.workflow_version,
                "policy_version": snapshot.policy.get("version", "embedded-default"),
                "component_snapshot": snapshot.digest,
                "node": node,
            },
            operation=operation,
        )

    def _skills_from_patch(self, skill_patch: dict[str, Any]) -> list[dict[str, Any]]:
        """Reconstruct a skill display list from the stored skill_patch.

        Return value is compatible with ``skills.retrieve_for_research()`` output
        so the UI and event payloads work unchanged.
        """
        skills: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source in (skill_patch.get("applied") or {}, skill_patch.get("deferred") or {}):
            for ref in source:
                name, _, version = ref.partition("@")
                if name not in seen:
                    seen.add(name)
                    skills.append({
                        "skill_id": "",
                        "name": name,
                        "version": version,
                        "description": "",
                        "evidence_policy": "",
                        "body": "",
                        "retrieval_score": 0.0,
                    })
        return skills

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
        started_at = datetime.now(timezone.utc)
        trace_id = trace_id or self.harness.new_trace_id()
        # Retrieval is deterministic for a (category, market) pair, so it runs
        # before the run's component snapshot instead of after the analysis node.
        # A retrieved skill's evidence_policy changes what the publication gate
        # accepts, so it belongs inside the fingerprinted policy rather than
        # applied behind the fingerprint's back.
        skill_patch: dict[str, Any] = {}
        existing_run = self.harness.runs.get_run(task_id)
        if existing_run and existing_run.get("component_snapshot"):
            component_snapshot = self.harness.component_snapshot_for_task(task_id)
            self._ensure_snapshot_plugins(component_snapshot)
            # A resumed run reuses the patch its run started with, so a restored
            # node sees the same policy it was computed under and is not re-run.
            skill_patch = dict(component_snapshot.policy.get("skill_patch") or {})
            # Rebuild skill display from the stored patch so the UI shows what
            # the gate actually applied, not a fresh (potentially different) retrieval.
            retrieved_skills = self._skills_from_patch(skill_patch)
        else:
            retrieved_skills = self.skills.retrieve_for_research(
                request.category, request.market, request.mode
            )
            active_policy = self.evolution.active_policy()
            effective_policy = dict(active_policy["policy"])
            skill_patch = self.skills.apply_evidence_policies(
                retrieved_skills, effective_policy, request.mode
            )
            component_snapshot = self.harness.create_component_snapshot(
                ScopeContext(task_id=task_id),
                {
                    "version": active_policy["version"],
                    "policy": effective_policy,
                    "skill_patch": skill_patch,
                },
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
                if node == "analyze" and retrieved_skills:
                    await board.publish_artifact("retrieved_skills", retrieved_skills, "skill-bank")
                    await board.publish_artifact("skill_policy_patch", skill_patch, "skill-bank")
                    await board.publish_event(
                        RuntimeEvent(
                            EventType.SKILL_RETRIEVED,
                            task_id,
                            "skill-bank",
                            f"Retrieved {len(retrieved_skills)} skills for decision compilation",
                            {
                                "skills": [s["name"] for s in retrieved_skills],
                                "applied": skill_patch.get("applied", {}),
                                "deferred": skill_patch.get("deferred", {}),
                            },
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
            self.harness.runs.set_result(task_id, result.model_dump(mode="json"))
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
            "error": run.get("error"),
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
            run = self.harness.runs.get_run(task_id)
            stored = run.get("result") if run else None
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
            self.harness.runs.set_result(task_id, result.model_dump(mode="json"))
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

        Unit economics, if provided, act as an additional gate: negative
        contribution margin forces VALIDATE regardless of other metrics.

        ``outcome`` acts as a weak tiebreaker: in the gray zone, a user-declared
        ``negative`` outcome pushes toward STOP while ``positive`` keeps VALIDATE.

        Evidence coverage "最小验证是否完成？" reflects whether the experiment
        was actually conducted (has real metrics), NOT whether results passed.
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

        if contract.validation_submitted:
            raise ValueError(
                "Validation results have already been submitted for this contract. "
                "Use /override if you need to change the verdict."
            )

        if (
            contract.experiment_budget is not None
            and result.actual_spend > contract.experiment_budget
        ):
            raise ValueError(
                f"实际花费 ¥{result.actual_spend:.0f} 超过本次实验预算 "
                f"¥{contract.experiment_budget:.0f}"
            )

        metrics = result.metrics
        criteria = contract.promotion_criteria

        # --- Unit economics gate (runs first — a broken model blocks GO) ---
        econ_verdict: DecisionVerdict | None = None
        econ_details: dict[str, Any] = {}
        if result.economics is not None:
            from .api_routes import _compute_unit_economics
            econ = _compute_unit_economics(result.economics)
            econ_details = {
                "contribution_margin_pct": econ.contribution_margin_pct,
                "contribution_profit": econ.contribution_profit,
                "break_even_price": econ.break_even_price,
                "landed_cost": econ.landed_cost,
                "max_cpc_at_target_margin": econ.max_cpc_at_target_margin,
            }
            if econ.contribution_margin_pct < 0:
                econ_verdict = DecisionVerdict.VALIDATE
            # If the selling price is below break-even, demand validation cannot
            # produce a sustainable business.
            if result.economics.selling_price < econ.break_even_price:
                econ_verdict = DecisionVerdict.STOP

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
            cpc_raw = metrics.get("cpc")
            if cpc_raw is None:
                promotion_failed.append("未提交 CPC，不能通过成本晋级门")
            else:
                cpc_value = float(cpc_raw)
                if cpc_value <= criteria.max_cpc:
                    promotion_passed.append(f"CPC ¥{cpc_value:.2f} ≤ ¥{criteria.max_cpc:.2f}")
                else:
                    promotion_failed.append(f"CPC ¥{cpc_value:.2f} > ¥{criteria.max_cpc:.2f}")

        if criteria.min_pain_confirmation_rate is not None:
            pain_rate = float(metrics.get("pain_confirmation_rate", 0))
            if pain_rate >= criteria.min_pain_confirmation_rate:
                promotion_passed.append(f"痛点确认率 {pain_rate:.0%} ≥ {criteria.min_pain_confirmation_rate:.0%}")
            else:
                promotion_failed.append(f"痛点确认率 {pain_rate:.0%} < {criteria.min_pain_confirmation_rate:.0%}")

        # --- Evidence confidence floor ---
        snapshot = self.harness.policy_for_task(task_id) or {}
        confidence_policy = dict(snapshot.get("policy") or {})
        confidence_floor = float(confidence_policy.get("minimum_evidence_confidence", 0.0) or 0.0)
        if confidence_floor > 0 and stored.cards:
            confidence = sum(card.confidence_score for card in stored.cards) / len(stored.cards)
            if confidence >= confidence_floor:
                promotion_passed.append(f"证据置信度 {confidence:.0%} ≥ {confidence_floor:.0%}")
            else:
                promotion_failed.append(f"证据置信度 {confidence:.0%} < {confidence_floor:.0%}")

        # --- Unit economics gate result ---
        if econ_details:
            if econ_details["contribution_margin_pct"] < 0:
                promotion_failed.append(
                    f"单位经济：贡献毛利 {econ_details['contribution_margin_pct']:.1f}% < 0，"
                    f"利润 ¥{econ_details['contribution_profit']:.2f}，盈亏平衡售价 ¥{econ_details['break_even_price']:.2f}"
                )
                if result.economics and result.economics.selling_price < econ_details["break_even_price"]:
                    promotion_failed.append(
                        f"售价 ¥{result.economics.selling_price:.2f} 低于盈亏平衡价 "
                        f"¥{econ_details['break_even_price']:.2f}，当前成本结构不可持续"
                    )
            elif econ_details["contribution_margin_pct"] > 0:
                promotion_passed.append(
                    f"单位经济：贡献毛利 {econ_details['contribution_margin_pct']:.1f}%，"
                    f"利润 ¥{econ_details['contribution_profit']:.2f}"
                )

        # --- Stop gates (abort threshold) ---
        stop_triggered: list[str] = []

        intent_raw = metrics.get("intent_rate")
        intent_submitted = intent_raw is not None

        if (
            intent_submitted
            and sample >= criteria.stop_sample_count
            and intent <= criteria.stop_intent_rate
        ):
            stop_triggered.append(
                f"意向率 {intent:.0%} ≤ 否决线 {criteria.stop_intent_rate:.0%} "
                f"（样本 {sample} ≥ {criteria.stop_sample_count}）"
            )

        # --- Three-state verdict ---
        if not promotion_failed and promotion_passed:
            system_verdict = DecisionVerdict.GO
        elif stop_triggered:
            system_verdict = DecisionVerdict.STOP
        else:
            # Gray zone: outcome acts as weak tiebreaker
            # negative → STOP (user says experiment failed, don't waste more money)
            # positive + unit economics OK → VALIDATE (close but keep going)
            # inconclusive → VALIDATE (default, need more data)
            if result.outcome == "negative" and not promotion_passed:
                system_verdict = DecisionVerdict.STOP
            else:
                system_verdict = DecisionVerdict.VALIDATE

        # Unit economics override: a broken model trumps promotion gates
        if econ_verdict is not None and system_verdict == DecisionVerdict.GO:
            system_verdict = econ_verdict

        # Market evidence gap guard (hybrid/real only)
        unresolved_market_gaps = [
            question
            for question in contract.evidence_coverage.gaps
            if "目标市场" in question
        ]
        if system_verdict == DecisionVerdict.GO and unresolved_market_gaps and stored.request.mode != "mock":
            system_verdict = DecisionVerdict.VALIDATE
            contract.allowed_investment = (
                contract.experiment_budget
                if contract.experiment_budget is not None
                else (min(round((contract.planned_investment or 10000) * 0.10, 0), 2000))
            )
            promotion_failed.append("目标市场证据仍不足，不能释放投入额度")

        # --- Apply verdict ---
        if system_verdict == DecisionVerdict.GO:
            contract.allowed_investment = contract.planned_investment
        elif system_verdict == DecisionVerdict.STOP:
            contract.allowed_investment = 0

        contract.system_verdict = system_verdict
        contract.verdict = system_verdict
        contract.validation_submitted = True
        contract.core_basis.append(
            f"验证结果：实际花费 ¥{result.actual_spend:.0f}，"
            f"实验结论={result.outcome}"
        )
        if econ_details:
            contract.core_basis.append(
                f"单位经济：贡献毛利 {econ_details['contribution_margin_pct']:.1f}%，"
                f"盈亏平衡 ¥{econ_details['break_even_price']:.2f}，"
                f"目标毛利允许 CPC ¥{econ_details['max_cpc_at_target_margin']:.2f}"
            )
        if promotion_passed:
            contract.core_basis.append("晋级门通过：" + "；".join(promotion_passed))
        if promotion_failed:
            contract.core_basis.append("晋级门未通过：" + "；".join(promotion_failed))
        if stop_triggered:
            contract.core_basis.append("否决条件触发：" + "；".join(stop_triggered))

        # --- Evidence coverage ---
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
        self.harness.runs.set_result(task_id, stored.model_dump(mode="json"))

        # Trace
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {
                "system_verdict": system_verdict.value,
                "actual_spend": result.actual_spend,
                "outcome": result.outcome,
                **({"economics": econ_details} if econ_details else {}),
            }
            self.harness.trace.write(run["trace_id"], task_id, "validation.submitted", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "validation.submitted", payload, "validation")

        return contract

    def override_contract(
        self, task_id: str, override: OverrideRequest
    ) -> DecisionContract:
        """Human override of a system verdict. Does NOT modify evidence coverage.

        This is a separate endpoint from submit_validation_result:
          - /validate-result = system re-evaluates with new metrics
          - /override = human explicitly overrides the system verdict
        """
        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")

        contract = stored.contract
        if contract.system_verdict is None:
            raise ValueError("Contract has no system verdict to override")
        if override.target_verdict == contract.system_verdict:
            raise ValueError(
                f"Override target ({override.target_verdict.value}) matches "
                f"system verdict — no override needed"
            )

        contract.system_verdict = contract.system_verdict  # unchanged
        contract.human_override = override.target_verdict
        contract.verdict = override.target_verdict
        contract.override_reason = override.reason
        contract.override_by = override.operator
        contract.override_at = datetime.now(timezone.utc)

        if override.target_verdict == DecisionVerdict.GO:
            contract.allowed_investment = contract.planned_investment
        elif override.target_verdict == DecisionVerdict.STOP:
            contract.allowed_investment = 0

        contract.core_basis.append(
            f"人工覆盖：系统判定={contract.system_verdict.value}，"
            f"人工覆盖为 {override.target_verdict.value}，"
            f"理由={override.reason}，操作人={override.operator}"
        )

        # Persist
        self.harness.memory.put("contracts", task_id, contract.model_dump(mode="json"))
        stored.contract = contract
        self.harness.memory.put("research_results", task_id, stored.model_dump(mode="json"))
        self.harness.runs.set_result(task_id, stored.model_dump(mode="json"))

        # Trace
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {
                "system_verdict": contract.system_verdict.value,
                "override": override.target_verdict.value,
                "reason": override.reason,
                "operator": override.operator,
            }
            self.harness.trace.write(run["trace_id"], task_id, "contract.override", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "contract.override", payload, "override")

        return contract

    def acknowledge_contract(self, task_id: str, operator: str = "demo-user") -> DecisionContract:
        """Persist a human acknowledgement of the current contract decision."""

        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")
        contract = stored.contract
        contract.acknowledged_at = datetime.now(timezone.utc)
        contract.acknowledged_by = operator
        contract.core_basis.append(f"人工确认：{contract.verdict.value}，操作人={operator}")
        stored.contract = contract
        self.harness.memory.put("contracts", task_id, contract.model_dump(mode="json"))
        self.harness.memory.put("research_results", task_id, stored.model_dump(mode="json"))
        self.harness.runs.set_result(task_id, stored.model_dump(mode="json"))
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {"verdict": contract.verdict.value, "operator": operator}
            self.harness.trace.write(run["trace_id"], task_id, "contract.acknowledged", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "contract.acknowledged", payload, "acknowledgement")
        return contract

    def update_execution_task(
        self, task_id: str, execution_task_id: str, status: str, owner: str | None = None
    ) -> DecisionContract:
        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")
        contract = stored.contract
        task = next((item for item in contract.execution_tasks if item.task_id == execution_task_id), None)
        if task is None:
            raise KeyError(execution_task_id)
        task.status = status
        if owner is not None:
            task.owner = owner
        stored.contract = contract
        self.harness.memory.put("contracts", task_id, contract.model_dump(mode="json"))
        self.harness.memory.put("research_results", task_id, stored.model_dump(mode="json"))
        self.harness.runs.set_result(task_id, stored.model_dump(mode="json"))
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {"execution_task_id": execution_task_id, "status": status, "owner": task.owner}
            self.harness.trace.write(run["trace_id"], task_id, "execution_task.updated", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "execution_task.updated", payload, "execution")
        return contract

    def create_execution_task(self, task_id: str, title: str, status: str = "todo",
                              owner: str | None = None, due_at: datetime | None = None) -> DecisionContract:
        from .models import ExecutionTask

        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")
        contract = stored.contract
        task = ExecutionTask(title=title, status=status, owner=owner, due_at=due_at)
        contract.execution_tasks.append(task)
        stored.contract = contract
        self.harness.memory.put("contracts", task_id, contract.model_dump(mode="json"))
        self.harness.memory.put("research_results", task_id, stored.model_dump(mode="json"))
        self.harness.runs.set_result(task_id, stored.model_dump(mode="json"))
        run = self.harness.runs.get_run(task_id)
        if run:
            payload = {"execution_task_id": task.task_id, "title": title, "status": status, "owner": owner}
            self.harness.trace.write(run["trace_id"], task_id, "execution_task.created", payload)
            self.harness.runs.record_event(task_id, run["trace_id"], "execution_task.created", payload, "execution")
        return contract

    def record_actual_outcome(self, task_id: str, request: "ActualOutcomeRequest") -> dict[str, Any]:
        """Close the loop: user reports what actually happened after the decision.

        This feeds the calibration dashboard (how often was the system right?)
        and gives the evolution engine real outcome data instead of synthetic fixtures.
        """
        from .models import ActualOutcomeRequest as Req

        stored = self.get_result(task_id)
        if not stored or not stored.contract:
            raise KeyError(f"No decision contract available for task {task_id}")
        contract = stored.contract
        record = {
            "outcome_id": str(uuid4()),
            "task_id": task_id,
            "contract_id": contract.contract_id,
            "system_verdict": (contract.system_verdict or contract.verdict).value,
            "actual_revenue": request.actual_revenue,
            "actual_profit": request.actual_profit,
            "actual_roi_pct": request.actual_roi_pct,
            "verdict_was_correct": request.verdict_was_correct,
            "notes": request.notes,
            "operator": request.operator,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
        self.harness.memory.record_actual_outcome(record)
        run = self.harness.runs.get_run(task_id)
        if run:
            self.harness.trace.write(run["trace_id"], task_id, "outcome.recorded", {
                "verdict_was_correct": record["verdict_was_correct"],
                "actual_roi_pct": record["actual_roi_pct"],
            })
        return record

    def calibration_summary(self) -> dict[str, Any]:
        return self.harness.memory.calibration_summary()

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        return self.harness.checkpoints.load(task_id)
