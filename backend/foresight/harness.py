from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


class TraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, trace_id: str, task_id: str, kind: str, payload: dict[str, Any]) -> None:
        record = {
            "trace_id": trace_id,
            "task_id": task_id,
            "kind": kind,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class MemoryStore:
    """SQLite-backed long-term task, card and feedback memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

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
            """)

    def put(self, namespace: str, key: str, value: Any) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO memories(namespace, memory_key, value_json, created_at) VALUES(?,?,?,?)",
                (namespace, key, json.dumps(value, ensure_ascii=False, default=str), datetime.now(timezone.utc).isoformat()),
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
                (feedback["feedback_id"], feedback["task_id"], feedback["card_id"], json.dumps(feedback, ensure_ascii=False, default=str), datetime.now(timezone.utc).isoformat()),
            )


class CheckpointStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, task_id: str, stage: str, payload: dict[str, Any]) -> Path:
        path = self.directory / f"{task_id}.json"
        document = {
            "task_id": task_id,
            "stage": stage,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def load(self, task_id: str) -> dict[str, Any] | None:
        path = self.directory / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class AgentHarness:
    """Runtime middleware for tracing, memory, checkpoints and tool policy."""

    def __init__(self, workdir: Path | str = ".foresight") -> None:
        root = Path(workdir)
        self.trace = TraceWriter(root / "traces.jsonl")
        self.memory = MemoryStore(root / "memory.db")
        self.checkpoints = CheckpointStore(root / "checkpoints")
        self.allowed_tools = {"mock_data", "statistics", "memory_read", "memory_write"}

    def new_trace_id(self) -> str:
        return str(uuid4())

    @contextmanager
    def agent_span(self, trace_id: str, task_id: str, agent: str) -> Iterator[None]:
        self.trace.write(trace_id, task_id, "agent.start", {"agent": agent})
        try:
            yield
        except Exception as exc:
            self.trace.write(trace_id, task_id, "agent.error", {"agent": agent, "error": str(exc)})
            raise
        else:
            self.trace.write(trace_id, task_id, "agent.done", {"agent": agent})

    def assert_tool_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise PermissionError(f"Tool not allowed by harness policy: {tool_name}")
