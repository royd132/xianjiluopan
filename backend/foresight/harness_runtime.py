from __future__ import annotations

import asyncio
import inspect
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator
from uuid import uuid4

from .extensions import (
    CapabilityGuard,
    ComponentSnapshot,
    PluginManager,
    ScopeContext,
    ScopedToolRegistry,
)
from .harness import CheckpointStore, MemoryStore, RunStore, TraceWriter, stable_hash


class AgentHarness:
    """Durable execution middleware built on injected persistence components."""

    runtime_version = "harness-v3"

    def __init__(self, workdir: Path | str = ".foresight") -> None:
        root = Path(workdir)
        self.trace = TraceWriter(root / "traces.jsonl")
        self.memory = MemoryStore(root / "memory.db")
        self.checkpoints = CheckpointStore(root / "checkpoints")
        self.runs = RunStore(root / "runs.db")
        self.tools = ScopedToolRegistry()
        self.plugins = PluginManager(self.tools)
        self.allowed_tools = {
            "mock_data",
            "hybrid_data",
            "real_data",
            "statistics",
            "memory_read",
            "memory_write",
        }
        self._guard_cleanup = self.tools.add_guard(
            CapabilityGuard(
                guard_id="core-allowed-tools",
                allowed_tools=frozenset(self.allowed_tools),
                reason="Tool not allowed by harness policy",
            )
        )

    def new_trace_id(self) -> str:
        return str(uuid4())

    @contextmanager
    def storage_scope(self) -> Iterator[None]:
        with ExitStack() as stack:
            stack.enter_context(self.memory.connection_scope())
            stack.enter_context(self.runs.connection_scope())
            yield

    @contextmanager
    def agent_span(self, trace_id: str, task_id: str, agent: str) -> Iterator[None]:
        self.trace.write(trace_id, task_id, "agent.start", {"agent": agent})
        self.runs.record_event(task_id, trace_id, "agent.start", {"agent": agent}, agent)
        try:
            yield
        except Exception as exc:
            payload = {"agent": agent, "error": str(exc)}
            self.trace.write(trace_id, task_id, "agent.error", payload)
            self.runs.record_event(task_id, trace_id, "agent.error", payload, agent)
            raise
        else:
            self.trace.write(trace_id, task_id, "agent.done", {"agent": agent})
            self.runs.record_event(task_id, trace_id, "agent.done", {"agent": agent}, agent)

    def assert_tool_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise PermissionError(f"Tool not allowed by harness policy: {tool_name}")

    def create_component_snapshot(
        self,
        scope: ScopeContext,
        policy: dict[str, Any],
    ) -> ComponentSnapshot:
        return self.plugins.snapshot(scope, policy)

    def component_snapshot_for_task(self, task_id: str) -> ComponentSnapshot:
        run = self.runs.get_run(task_id)
        if not run:
            raise KeyError(f"Component snapshot is unavailable for task {task_id}")
        if not run.get("component_snapshot"):
            request = run.get("request", {})
            active_policy = self.memory.active_policy()
            snapshot = self.create_component_snapshot(
                ScopeContext(
                    tenant_id=str(request.get("workspace_id", "default")),
                    preset_id=str(request.get("market", "global")),
                    task_id=task_id,
                ),
                {
                    "version": active_policy["version"] if active_policy else "embedded-default",
                    "policy": active_policy["policy"] if active_policy else {},
                },
            )
            self.runs.set_component_snapshot(task_id, snapshot.as_dict())
            return snapshot
        return ComponentSnapshot.from_dict(run["component_snapshot"])

    def scope_for_task(self, task_id: str) -> ScopeContext:
        snapshot = self.component_snapshot_for_task(task_id)
        return ScopeContext.from_dict(snapshot.scope)

    def policy_for_task(self, task_id: str) -> dict[str, Any]:
        return dict(self.component_snapshot_for_task(task_id).policy)

    async def call_tool(
        self,
        tool_name: str,
        agent: str,
        trace_id: str,
        task_id: str,
        **kwargs: Any,
    ) -> Any:
        snapshot = self.component_snapshot_for_task(task_id)
        scope = ScopeContext.from_dict(snapshot.scope)
        tool_identity = snapshot.tools.get(tool_name, {})
        pinned = tool_identity.get("registration_id")
        definition = self.tools.get(
            tool_name,
            agent,
            scope,
            pinned,
            tool_identity.get("plugin_id"),
            tool_identity.get("plugin_version"),
            tool_identity.get("scope_key"),
        )
        inspect.signature(definition.handler).bind(**kwargs)
        safe_args = {key: str(value)[:500] for key, value in kwargs.items()}
        start_payload = {
            "tool": tool_name,
            "agent": agent,
            "args": safe_args,
            "plugin_id": tool_identity.get("plugin_id"),
            "plugin_version": tool_identity.get("plugin_version"),
            "component_snapshot": snapshot.digest,
        }
        self.trace.write(trace_id, task_id, "tool.start", start_payload)
        self.runs.record_event(task_id, trace_id, "tool.start", start_payload, agent)
        try:
            result = definition.handler(**kwargs)
            if inspect.isawaitable(result):
                result = await asyncio.wait_for(result, timeout=definition.timeout_seconds)
        except Exception as exc:
            payload = {"tool": tool_name, "agent": agent, "error": str(exc)}
            self.trace.write(trace_id, task_id, "tool.error", payload)
            self.runs.record_event(task_id, trace_id, "tool.error", payload, agent)
            raise
        summary = {"tool": tool_name, "agent": agent, "result_hash": stable_hash(result)}
        self.trace.write(trace_id, task_id, "tool.done", summary)
        self.runs.record_event(task_id, trace_id, "tool.done", summary, agent)
        return result

    async def run_node(
        self,
        task_id: str,
        trace_id: str,
        node: str,
        input_value: Any,
        operation: Callable[[], Awaitable[Any]],
        max_attempts: int = 2,
        timeout_seconds: float = 45.0,
    ) -> Any:
        if self.runs.is_cancel_requested(task_id):
            raise asyncio.CancelledError(f"Task {task_id} was cancelled")
        input_hash = stable_hash(input_value)
        previous = self.runs.node_state(task_id, node)
        if previous and previous["status"] == "completed" and previous["input_hash"] == input_hash:
            self.runs.record_event(task_id, trace_id, "node.restored", {"node": node}, node)
            return previous["output"]

        for attempt in range(1, max_attempts + 1):
            self.runs.set_run_status(task_id, "running", node)
            self.runs.save_node(task_id, node, "running", attempt, input_hash)
            self.runs.record_event(task_id, trace_id, "node.started", {"attempt": attempt}, node)
            self.trace.write(trace_id, task_id, "node.started", {"node": node, "attempt": attempt})
            try:
                output = await asyncio.wait_for(operation(), timeout=timeout_seconds)
            except asyncio.CancelledError:
                self.runs.save_node(task_id, node, "cancelled", attempt, input_hash, error="cancelled")
                self.runs.set_run_status(task_id, "cancelled", node, "cancelled")
                self.runs.record_event(task_id, trace_id, "node.cancelled", {"attempt": attempt}, node)
                raise
            except Exception as exc:
                self.runs.save_node(task_id, node, "failed", attempt, input_hash, error=str(exc))
                self.runs.record_event(
                    task_id,
                    trace_id,
                    "node.retry" if attempt < max_attempts else "node.failed",
                    {"attempt": attempt, "error": str(exc)},
                    node,
                )
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(0)
            else:
                self.runs.save_node(task_id, node, "completed", attempt, input_hash, output=output)
                self.runs.record_event(task_id, trace_id, "node.completed", {"attempt": attempt}, node)
                self.trace.write(trace_id, task_id, "node.completed", {"node": node, "attempt": attempt})
                return output
        raise RuntimeError(f"Node {node} exhausted attempts")
