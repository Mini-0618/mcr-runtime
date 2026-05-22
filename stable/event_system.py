"""
Event System
Event-driven state changes only
"""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class EventType(str, Enum):
    USER_INPUT = "USER_INPUT"
    GOAL_CREATED = "GOAL_CREATED"
    GOAL_UPDATED = "GOAL_UPDATED"
    GOAL_COMPLETED = "GOAL_COMPLETED"
    TASK_CREATED = "TASK_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    MEMORY_ACTIVATED = "MEMORY_ACTIVATED"
    MEMORY_STORED = "MEMORY_STORED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    STATE_COMPRESSED = "STATE_COMPRESSED"
    PLAN_UPDATED = "PLAN_UPDATED"
    OBSERVATION_ADDED = "OBSERVATION_ADDED"
    INTERNAL_REASONING = "INTERNAL_REASONING"


class Event:
    def __init__(
        self,
        event_type: EventType,
        payload: dict,
        source: str = "system",
        correlation_id: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.type = event_type
        self.payload = payload
        self.source = source
        self.timestamp = datetime.now().isoformat()
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


class EventQueue:
    def __init__(self, path: str):
        self.path = path
        self.queue: list[Event] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.queue = [self._dict_to_event(e) for e in data.get("events", [])]

    def _dict_to_event(self, d: dict) -> Event:
        """Convert dict back to Event."""
        e = Event(
            event_type=EventType(d["type"]),
            payload=d["payload"],
            source=d.get("source", "system"),
            correlation_id=d.get("correlation_id"),
        )
        e.id = d.get("id", e.id)
        e.timestamp = d.get("timestamp", e.timestamp)
        return e

    def push(self, event: Event) -> None:
        """Add event to queue."""
        self.queue.append(event)

    def pop(self, max_count: int = 20) -> list[Event]:
        """Get and remove events from queue."""
        events = self.queue[:max_count]
        self.queue = self.queue[max_count:]
        return events

    def peek(self, max_count: int = 20) -> list[Event]:
        """View events without removing."""
        return self.queue[:max_count]

    def size(self) -> int:
        return len(self.queue)

    def save(self) -> None:
        """Persist queue to disk."""
        data = {"events": [e.to_dict() for e in self.queue]}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_by_type(self, event_type: EventType) -> list[Event]:
        """Get all events of a specific type."""
        return [e for e in self.queue if e.type == event_type]


def create_event(
    event_type: EventType,
    payload: dict,
    source: str = "system",
) -> Event:
    return Event(event_type=event_type, payload=payload, source=source)
