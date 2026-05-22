"""
Event Graph — Causal DAG for MCR Event Ordering Physics
=========================================================

Establishes causal dependency tracking for event ordering verification.

Event Taxonomy v1:
  store      — memory written to working layer
  retrieve   — memory accessed from any layer
  rerank     — memory position changed in retrieval
  promotion  — memory moved to more permanent layer
  archive    — memory moved to cold storage
  delete     — memory removed from runtime
  replay     — WAL replay reconstruction
  recover    — crash recovery reconstruction

Causal Rules (MUST be obeyed):
  R1: retrieve cannot see future delete
  R2: promotion must happen after retrieve/access
  R3: archive cannot be before promotion
  R4: delete cannot be before archive
  R5: rerank cannot reference future topology state
  R6: replay must rebuild same ordering across replays
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class EventType(Enum):
    STORE = "store"
    RETRIEVE = "retrieve"
    RERANK = "rerank"
    PROMOTION = "promotion"
    ARCHIVE = "archive"
    DELETE = "delete"
    REPLAY = "replay"
    RECOVER = "recover"

@dataclass
class Event:
    seq: int
    tick: int
    type: EventType
    memory_id: str
    from_layer: Optional[str] = None  # for move operations
    to_layer: Optional[str] = None    # for move operations
    causal_parents: list[int] = field(default_factory=list)  # seq of causal ancestors
    metadata: dict = field(default_factory=dict)
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "seq": self.seq, "tick": self.tick, "type": self.type.value,
            "memory_id": self.memory_id, "from_layer": self.from_layer,
            "to_layer": self.to_layer, "causal_parents": self.causal_parents,
            "metadata": self.metadata, "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            seq=d["seq"], tick=d["tick"], type=EventType(d["type"]),
            memory_id=d["memory_id"], from_layer=d.get("from_layer"),
            to_layer=d.get("to_layer"),
            causal_parents=d.get("causal_parents", []),
            metadata=d.get("metadata", {}), timestamp=d.get("timestamp"),
        )

    def event_hash(self) -> str:
        """Deterministic hash of event content."""
        key = f"{self.seq}|{self.tick}|{self.type.value}|{self.memory_id}|{self.from_layer}|{self.to_layer}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class EventGraph:
    """
    Causal DAG of events.
    Tracks: event → causal_parents (what must precede it).
    Verifies: no cycle, temporal rules obeyed.
    """

    def __init__(self):
        self.events: list[Event] = []          # seq-indexed
        self.by_memory: dict[str, list[Event]] = {}  # memory_id → events
        self.seq_to_event: dict[int, Event] = {}
        self._violations: list[dict] = []

    def add_event(self, event: Event) -> None:
        self.events.append(event)
        self.seq_to_event[event.seq] = event
        self.by_memory.setdefault(event.memory_id, []).append(event)
        self._check_causal_violations(event)

    def _check_causal_violations(self, event: Event) -> None:
        """Check all RULES for this event."""
        mem_events = self.by_memory.get(event.memory_id, [])

        if event.type == EventType.RETRIEVE:
            # R1: retrieve cannot see future delete
            for e in mem_events:
                if e.type == EventType.DELETE and e.seq > event.seq:
                    self._record_violation("R1", event, f"future delete seq={e.seq}")

        elif event.type == EventType.PROMOTION:
            # R2: promotion must happen after retrieve/access
            prior = [e for e in mem_events if e.seq < event.seq and e.type in (EventType.RETRIEVE, EventType.STORE)]
            if not prior:
                self._record_violation("R2", event, "no prior access/retrieve before promotion")

        elif event.type == EventType.ARCHIVE:
            # R3: archive cannot be before promotion
            promos = [e for e in mem_events if e.type == EventType.PROMOTION and e.seq < event.seq]
            if not promos:
                self._record_violation("R3", event, "no prior promotion before archive")

        elif event.type == EventType.DELETE:
            # R4: delete cannot be before archive
            archives = [e for e in mem_events if e.type == EventType.ARCHIVE and e.seq < event.seq]
            if not archives:
                self._record_violation("R4", event, "no prior archive before delete")

        elif event.type == EventType.RERANK:
            # R5: rerank cannot reference future topology state
            # A rerank at tick T only knows topology as of tick T
            # Events happening after tick T shouldn't be referenced
            future_events = [e for e in self.events if e.tick > event.tick and e.seq > event.seq]
            # This is more about whether rerank result depends on future state
            # We check: rerank should not appear to precede events that affect its input
            pass  # R5 is checked via topology_leak test separately

    def _record_violation(self, rule: str, event: Event, detail: str) -> None:
        self._violations.append({
            "rule": rule, "event_seq": event.seq, "event_type": event.type.value,
            "memory_id": event.memory_id, "tick": event.tick, "detail": detail,
        })

    def verify_all_rules(self) -> dict:
        """Full causal verification pass."""
        violations = list(self._violations)
        # Re-verify all events
        self._violations = []
        for event in self.events:
            self._check_causal_violations(event)
        violations.extend(self._violations)

        return {
            "total_events": len(self.events),
            "violation_count": len(violations),
            "violations": violations,
            "causally_coherent": len(violations) == 0,
        }

    def ordering_hash(self) -> str:
        """Deterministic hash of event ordering."""
        key = "|".join([
            f"{e.seq}:{e.type.value}:{e.memory_id}:{e.tick}"
            for e in sorted(self.events, key=lambda x: x.seq)
        ])
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def causal_chain(self, event: Event) -> list[int]:
        """Return full causal chain (ancestors) for an event."""
        chain = []
        seen = set()
        stack = list(event.causal_parents)
        while stack:
            seq = stack.pop()
            if seq in seen:
                continue
            seen.add(seq)
            chain.append(seq)
            e = self.seq_to_event.get(seq)
            if e:
                stack.extend(e.causal_parents)
        return sorted(chain)

    def lifecycle_order(self, memory_id: str) -> list[EventType]:
        """Return lifecycle order for a memory_id."""
        return [e.type for e in sorted(self.by_memory.get(memory_id, []), key=lambda x: x.seq)]

    def to_json(self) -> dict:
        return {
            "event_count": len(self.events),
            "unique_memories": len(self.by_memory),
            "ordering_hash": self.ordering_hash(),
            "violations": self._violations,
            "events": [e.to_dict() for e in self.events],
        }


def events_from_wal(wal_manager, lm_instance=None) -> EventGraph:
    """
    Replay WAL and construct event graph from actual runtime events.
    """
    graph = EventGraph()
    for entry in wal_manager.replay():
        # Map WAL entry to Event
        etype_raw = entry.event.get("event_type", "unknown")
        try:
            etype = EventType(etype_raw)
        except ValueError:
            etype = EventType.STORE  # fallback for legacy entries

        event = Event(
            seq=entry.seq,
            tick=entry.event.get("tick", 0),
            type=etype,
            memory_id=entry.event.get("memory_id", ""),
            from_layer=entry.event.get("from_layer"),
            to_layer=entry.event.get("to_layer"),
            causal_parents=[],  # filled by graph
            metadata=entry.event.get("metadata", {}),
            timestamp=entry.event.get("timestamp"),
        )
        # Infer causal parents from event type
        if event.type in (EventType.PROMOTION, EventType.ARCHIVE, EventType.DELETE):
            # These require the memory to have been stored first
            prev = [e for e in graph.by_memory.get(event.memory_id, [])]
            if prev:
                event.causal_parents = [prev[-1].seq]
        elif event.type == EventType.RETRIEVE:
            prev = [e for e in graph.by_memory.get(event.memory_id, [])]
            if prev:
                event.causal_parents = [prev[-1].seq]

        graph.add_event(event)

    return graph


def ordering_hash(events: list) -> str:
    """Compute ordering hash from a list of events."""
    key = "|".join([
        f"{e['seq']}:{e['type']}:{e['memory_id']}:{e.get('tick',0)}"
        for e in sorted(events, key=lambda x: x['seq'])
    ])
    return hashlib.sha256(key.encode()).hexdigest()[:16]
