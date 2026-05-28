"""
MCR Minimal Demo — examples/minimal_mcr.py

MCR core concept in ~200 lines:
  Memory Event -> WAL -> Reducer -> Runtime State -> Replay Verification

This is a self-contained, dependency-free implementation.
Use this to understand the fundamental MCR guarantee.

Run:
    python3 examples/minimal_mcr.py
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import hashlib
import time


# =========================
# Event
# =========================

@dataclass(frozen=True)
class MemoryEvent:
    seq: int
    tick: int
    type: str
    memory_id: str
    payload: dict
    timestamp: float


# =========================
# WAL
# =========================

class WAL:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seq = self._load_last_seq()

    def _load_last_seq(self) -> int:
        if not self.path.exists():
            return 0

        last = 0
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                    last = max(last, event["seq"])
                except Exception:
                    continue
        return last

    def append(self, event_type: str, memory_id: str, payload: dict, tick: int) -> MemoryEvent:
        self.seq += 1

        event = MemoryEvent(
            seq=self.seq,
            tick=tick,
            type=event_type,
            memory_id=memory_id,
            payload=payload,
            timestamp=time.time(),
        )

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

        return event

    def read_all(self) -> list[MemoryEvent]:
        if not self.path.exists():
            return []

        events = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = json.loads(line)
                events.append(MemoryEvent(**raw))
        return events


# =========================
# Runtime State
# =========================

@dataclass
class RuntimeState:
    working: dict
    episodic: dict
    archive: dict

    @staticmethod
    def empty():
        return RuntimeState(
            working={},
            episodic={},
            archive={},
        )

    def to_dict(self):
        return {
            "working": self.working,
            "episodic": self.episodic,
            "archive": self.archive,
        }

    def hash(self) -> str:
        data = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


# =========================
# Reducer
# =========================

def reduce_event(state: RuntimeState, event: MemoryEvent) -> RuntimeState:
    """
    Pure reducer:
    state(t+1) = reduce_event(state(t), event)

    No hidden mutation.
    No random behavior.
    No external dependency.
    """

    if event.type == "memory_append":
        state.working[event.memory_id] = {
            "id": event.memory_id,
            "content": event.payload["content"],
            "tags": event.payload.get("tags", []),
            "created_tick": event.tick,
            "last_access_tick": event.tick,
        }

    elif event.type == "memory_access":
        item = state.working.get(event.memory_id) or state.episodic.get(event.memory_id)
        if item:
            item["last_access_tick"] = event.tick
            item["access_count"] = item.get("access_count", 0) + 1

    elif event.type == "memory_promote":
        item = state.working.pop(event.memory_id, None)
        if item:
            item["promoted_tick"] = event.tick
            state.episodic[event.memory_id] = item

    elif event.type == "memory_archive":
        item = state.episodic.pop(event.memory_id, None)
        if item:
            item["archived_tick"] = event.tick
            state.archive[event.memory_id] = item

    elif event.type == "memory_tombstone":
        state.working.pop(event.memory_id, None)
        state.episodic.pop(event.memory_id, None)
        state.archive.pop(event.memory_id, None)

    else:
        raise ValueError(f"Unknown event type: {event.type}")

    return state


def replay(events: list[MemoryEvent]) -> RuntimeState:
    state = RuntimeState.empty()

    for event in events:
        state = reduce_event(state, event)

    return state


# =========================
# Runtime Engine
# =========================

class MCRRuntime:
    def __init__(self, wal_path: str):
        self.wal = WAL(wal_path)
        self.state = replay(self.wal.read_all())
        self.tick = 0

    def append_memory(self, memory_id: str, content: str, tags=None):
        self.tick += 1

        event = self.wal.append(
            event_type="memory_append",
            memory_id=memory_id,
            payload={
                "content": content,
                "tags": tags or [],
            },
            tick=self.tick,
        )

        self.state = reduce_event(self.state, event)

    def access_memory(self, memory_id: str):
        self.tick += 1

        event = self.wal.append(
            event_type="memory_access",
            memory_id=memory_id,
            payload={},
            tick=self.tick,
        )

        self.state = reduce_event(self.state, event)

    def promote_memory(self, memory_id: str):
        self.tick += 1

        event = self.wal.append(
            event_type="memory_promote",
            memory_id=memory_id,
            payload={},
            tick=self.tick,
        )

        self.state = reduce_event(self.state, event)

    def archive_memory(self, memory_id: str):
        self.tick += 1

        event = self.wal.append(
            event_type="memory_archive",
            memory_id=memory_id,
            payload={},
            tick=self.tick,
        )

        self.state = reduce_event(self.state, event)

    def tombstone_memory(self, memory_id: str):
        self.tick += 1

        event = self.wal.append(
            event_type="memory_tombstone",
            memory_id=memory_id,
            payload={},
            tick=self.tick,
        )

        self.state = reduce_event(self.state, event)

    def verify_replay(self) -> bool:
        replayed = replay(self.wal.read_all())
        return self.state.hash() == replayed.hash()


# =========================
# Demo
# =========================

def main():
    wal_path = "tmp/mcr_demo.wal.jsonl"

    # Clean up old demo
    Path(wal_path).unlink(missing_ok=True)

    runtime = MCRRuntime(wal_path)

    runtime.append_memory(
        memory_id="mem_001",
        content="User is interested in AI agent memory systems.",
        tags=["agent", "memory"],
    )

    runtime.access_memory("mem_001")
    runtime.promote_memory("mem_001")
    runtime.archive_memory("mem_001")

    print("=== MCR Runtime State ===")
    print(json.dumps(runtime.state.to_dict(), indent=2, ensure_ascii=False))

    print("\n=== Replay Verification ===")
    print("Runtime state hash:", runtime.state.hash())

    replayed_state = replay(runtime.wal.read_all())
    print("Replay state hash: ", replayed_state.hash())

    if runtime.verify_replay():
        print("Result: PASS — replay state matches runtime state")
    else:
        print("Result: FAIL — replay state diverged")


if __name__ == "__main__":
    main()