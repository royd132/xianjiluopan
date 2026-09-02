from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

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


class _SqliteBase:
    """Shared SQLite connection management — ContextVar for async safety."""

    def __init__(self, path: Path, context_name: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_context: ContextVar[sqlite3.Connection | None] = ContextVar(
            context_name, default=None
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


class MemoryStore(_SqliteBase):
    """SQLite-backed memory plus the durable evolution registry."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"memory-store-{id(self)}")
        self._init_db()

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


class RunStore(_SqliteBase):
    """Append-only run ledger plus node-level recovery state."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"run-store-{id(self)}")
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
