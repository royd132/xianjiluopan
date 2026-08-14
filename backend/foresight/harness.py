from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import sqlite3
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator
from uuid import uuid4

from .extensions import (
    CapabilityGuard,
    ComponentSnapshot,
    PluginManager,
    ScopeContext,
    ScopedToolRegistry,
    ToolDefinition,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def open_sqlite(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


class TraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, trace_id: str, task_id: str, kind: str, payload: dict[str, Any]) -> None:
        record = {
            "trace_id": trace_id,
            "task_id": task_id,
            "kind": kind,
            "timestamp": utc_now(),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class MemoryStore:
    """SQLite-backed memory plus the durable evolution registry."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_context: ContextVar[sqlite3.Connection | None] = ContextVar(
            f"memory-store-{id(self)}", default=None
        )
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        active = self._connection_context.get()
        if active is not None:
            try:
                yield active
                active.commit()
            except Exception:
                active.rollback()
                raise
            return
        connection = open_sqlite(self.path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def connection_scope(self) -> Iterator[None]:
        connection = open_sqlite(self.path)
        token = self._connection_context.set(connection)
        try:
            yield
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._connection_context.reset(token)
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(namespace, memory_key)
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    card_id TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS failure_cases (
                    failure_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    card_id TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version TEXT PRIMARY KEY,
                    parent_version TEXT,
                    policy_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS evolution_runs (
                    run_id TEXT PRIMARY KEY,
                    baseline_version TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def put(self, namespace: str, key: str, value: Any) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO memories(namespace, memory_key, value_json, created_at) VALUES(?,?,?,?)",
                (namespace, key, json.dumps(value, ensure_ascii=False, default=str), utc_now()),
            )

    def get(self, namespace: str, key: str) -> Any | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM memories WHERE namespace=? AND memory_key=?", (namespace, key)
            ).fetchone()
        return json.loads(row["value_json"]) if row else None

    def append_feedback(self, feedback: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO feedback(feedback_id, task_id, card_id, value_json, created_at) VALUES(?,?,?,?,?)",
                (
                    feedback["feedback_id"],
                    feedback["task_id"],
                    feedback["card_id"],
                    json.dumps(feedback, ensure_ascii=False, default=str),
                    utc_now(),
                ),
            )

    def list_feedback(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT value_json FROM feedback ORDER BY created_at DESC").fetchall()
        return [json.loads(row["value_json"]) for row in rows]

    def append_failure_case(self, failure: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO failure_cases(
                    failure_id, task_id, card_id, failure_type, payload_json, status, created_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    failure["failure_id"],
                    failure["task_id"],
                    failure["card_id"],
                    failure["failure_type"],
                    json.dumps(failure, ensure_ascii=False, default=str),
                    failure.get("status", "open"),
                    failure.get("created_at", utc_now()),
                ),
            )

    def list_failure_cases(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json, status FROM failure_cases"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status=?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        failures = []
        for row in rows:
            item = json.loads(row["payload_json"])
            item["status"] = row["status"]
            failures.append(item)
        return failures

    def resolve_failures(self, failure_ids: list[str]) -> None:
        if not failure_ids:
            return
        placeholders = ",".join("?" for _ in failure_ids)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE failure_cases SET status='resolved', resolved_at=? WHERE failure_id IN ({placeholders})",
                (utc_now(), *failure_ids),
            )

    def save_policy(self, version: str, policy: dict[str, Any], status: str, parent_version: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO policy_versions(
                    version, parent_version, policy_json, status, created_at, activated_at
                ) VALUES(?,?,?,?,?,COALESCE((SELECT activated_at FROM policy_versions WHERE version=?), NULL))""",
                (version, parent_version, json.dumps(policy, ensure_ascii=False), status, utc_now(), version),
            )

    def get_policy(self, version: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version, parent_version, policy_json, status, created_at, activated_at FROM policy_versions WHERE version=?",
                (version,),
            ).fetchone()
        if not row:
            return None
        return {**dict(row), "policy": json.loads(row["policy_json"])}

    def active_policy(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT version, parent_version, policy_json, status, created_at, activated_at
                FROM policy_versions WHERE status='active' ORDER BY activated_at DESC LIMIT 1"""
            ).fetchone()
        if not row:
            return None
        return {**dict(row), "policy": json.loads(row["policy_json"])}

    def list_policies(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT version, parent_version, policy_json, status, created_at, activated_at FROM policy_versions ORDER BY created_at DESC"
            ).fetchall()
        return [{**dict(row), "policy": json.loads(row["policy_json"])} for row in rows]

    def activate_policy(self, version: str) -> None:
        with self._connect() as connection:
            candidate = connection.execute(
                "SELECT status FROM policy_versions WHERE version=?", (version,)
            ).fetchone()
            if not candidate:
                raise KeyError(version)
            if candidate["status"] not in {"ready", "active", "retired"}:
                raise ValueError(f"Policy {version} has not passed the evaluation gate")
            connection.execute("UPDATE policy_versions SET status='retired' WHERE status='active'")
            connection.execute(
                "UPDATE policy_versions SET status='active', activated_at=? WHERE version=?", (utc_now(), version)
            )

    def record_evolution_run(self, record: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO evolution_runs(run_id, baseline_version, candidate_version, decision, metrics_json, created_at) VALUES(?,?,?,?,?,?)",
                (
                    record["run_id"],
                    record["baseline_version"],
                    record["candidate_version"],
                    record["decision"],
                    json.dumps(record["metrics"], ensure_ascii=False),
                    record.get("created_at", utc_now()),
                ),
            )

    def list_evolution_runs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, baseline_version, candidate_version, decision, metrics_json, created_at FROM evolution_runs ORDER BY created_at DESC"
            ).fetchall()
        return [{**dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]


class RunStore:
    """Append-only run ledger plus node-level recovery state."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_context: ContextVar[sqlite3.Connection | None] = ContextVar(
            f"run-store-{id(self)}", default=None
        )
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    task_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_node TEXT,
                    runtime_fingerprint TEXT NOT NULL,
                    component_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    task_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    node TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS node_checkpoints (
                    task_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    input_hash TEXT NOT NULL,
                    output_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, node)
                );
            """)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(runs)").fetchall()
            }
            if "component_snapshot_json" not in columns:
                connection.execute(
                    "ALTER TABLE runs ADD COLUMN component_snapshot_json TEXT NOT NULL DEFAULT '{}'"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        active = self._connection_context.get()
        if active is not None:
            try:
                yield active
                active.commit()
            except Exception:
                active.rollback()
                raise
            return
        connection = open_sqlite(self.path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def connection_scope(self) -> Iterator[None]:
        connection = open_sqlite(self.path)
        token = self._connection_context.set(connection)
        try:
            yield
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._connection_context.reset(token)
            connection.close()

    def start_run(
        self,
        task_id: str,
        trace_id: str,
        request: dict[str, Any],
        runtime_fingerprint: str,
        component_snapshot: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        snapshot_json = json.dumps(component_snapshot or {}, ensure_ascii=False, default=str)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO runs(
                    task_id, trace_id, request_json, status, runtime_fingerprint,
                    component_snapshot_json, started_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    task_id,
                    trace_id,
                    json.dumps(request, ensure_ascii=False),
                    "running",
                    runtime_fingerprint,
                    snapshot_json,
                    now,
                    now,
                ),
            )
            connection.execute(
                """UPDATE runs
                SET status='running', error=NULL, updated_at=?,
                    component_snapshot_json=CASE
                        WHEN component_snapshot_json='{}' THEN ?
                        ELSE component_snapshot_json
                    END
                WHERE task_id=?""",
                (now, snapshot_json, task_id),
            )

    def get_run(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["request"] = json.loads(item.pop("request_json"))
        item["component_snapshot"] = json.loads(item.pop("component_snapshot_json") or "{}")
        return item

    def set_run_status(self, task_id: str, status: str, current_node: str | None = None, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status=?, current_node=?, error=?, updated_at=? WHERE task_id=?",
                (status, current_node, error, utc_now(), task_id),
            )

    def set_component_snapshot(self, task_id: str, snapshot: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET component_snapshot_json=?, updated_at=? WHERE task_id=?",
                (json.dumps(snapshot, ensure_ascii=False, default=str), utc_now(), task_id),
            )

    def record_event(
        self,
        task_id: str,
        trace_id: str,
        kind: str,
        payload: dict[str, Any],
        node: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO run_events(event_id, task_id, trace_id, kind, node, payload_json, created_at) VALUES(?,?,?,?,?,?,?)",
                (str(uuid4()), task_id, trace_id, kind, node, json.dumps(payload, ensure_ascii=False, default=str), utc_now()),
            )

    def list_events(self, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sequence, event_id, trace_id, kind, node, payload_json, created_at FROM run_events WHERE task_id=? ORDER BY sequence",
                (task_id,),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def node_state(self, task_id: str, node: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM node_checkpoints WHERE task_id=? AND node=?", (task_id, node)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["output"] = json.loads(item["output_json"]) if item.get("output_json") else None
        return item

    def save_node(
        self,
        task_id: str,
        node: str,
        status: str,
        attempts: int,
        input_hash: str,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO node_checkpoints(
                    task_id, node, status, attempts, input_hash, output_json, error, updated_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    task_id,
                    node,
                    status,
                    attempts,
                    input_hash,
                    json.dumps(output, ensure_ascii=False, default=str) if output is not None else None,
                    error,
                    utc_now(),
                ),
            )

    def request_cancel(self, task_id: str) -> None:
        run = self.get_run(task_id)
        if not run:
            raise KeyError(task_id)
        self.set_run_status(task_id, "cancel_requested", run.get("current_node"))

    def is_cancel_requested(self, task_id: str) -> bool:
        run = self.get_run(task_id)
        return bool(run and run["status"] == "cancel_requested")


class CheckpointStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, task_id: str, stage: str, payload: dict[str, Any]) -> Path:
        path = self.directory / f"{task_id}.json"
        document = {"task_id": task_id, "stage": stage, "saved_at": utc_now(), "payload": payload}
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def load(self, task_id: str) -> dict[str, Any] | None:
        path = self.directory / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class AgentHarness:
    """Durable runtime middleware for nodes, tools, tracing and evolution state."""

    runtime_version = "harness-v3"

    def __init__(self, workdir: Path | str = ".foresight") -> None:
        root = Path(workdir)
        self.trace = TraceWriter(root / "traces.jsonl")
        self.memory = MemoryStore(root / "memory.db")
        self.checkpoints = CheckpointStore(root / "checkpoints")
        self.runs = RunStore(root / "runs.db")
        self.tools = ScopedToolRegistry()
        self.plugins = PluginManager(self.tools)
        self.allowed_tools = {"mock_data", "statistics", "memory_read", "memory_write"}
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
