from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator
from uuid import uuid4


class EventType(str, Enum):
    TASK_STARTED = "task.started"
    AGENT_STARTED = "agent.started"
    ARTIFACT_PUBLISHED = "artifact.published"
    AGENT_COMPLETED = "agent.completed"
    GATE_PASSED = "gate.passed"
    CHECKPOINT_SAVED = "checkpoint.saved"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    FEEDBACK_RECORDED = "feedback.recorded"


@dataclass(slots=True)
class RuntimeEvent:
    event_type: EventType
    task_id: str
    agent: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "agent": self.agent,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class CollaborationBlackboard:
    """Shared artifact board plus an event stream for loosely coupled agents."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.artifacts: dict[str, Any] = {}
        self.events: list[RuntimeEvent] = []
        self._subscribers: list[asyncio.Queue[RuntimeEvent]] = []
        self._lock = asyncio.Lock()

    async def publish_event(self, event: RuntimeEvent) -> None:
        async with self._lock:
            self.events.append(event)
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(event)

    async def publish_artifact(self, key: str, value: Any, agent: str) -> None:
        async with self._lock:
            self.artifacts[key] = value
        await self.publish_event(RuntimeEvent(
            event_type=EventType.ARTIFACT_PUBLISHED,
            task_id=self.task_id,
            agent=agent,
            message=f"Artifact ready: {key}",
            data={"artifact": key},
        ))

    def read(self, key: str, default: Any = None) -> Any:
        return self.artifacts.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self.artifacts)

    async def subscribe(self) -> AsyncIterator[RuntimeEvent]:
        queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            for event in self.events:
                yield event
            while True:
                event = await queue.get()
                yield event
                if event.event_type in {EventType.TASK_COMPLETED, EventType.TASK_FAILED}:
                    break
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
