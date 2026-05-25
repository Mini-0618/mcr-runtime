"""
events.py — MCR Event Model and Schemas

Canonical home for:
- MCREvent dataclass
- Event type registry (ALLOWED_EVENT_TYPES)
- Event payload schemas (EVENT_SCHEMAS)
- Forbidden payload fields (FORBIDDEN_FIELDS)
- Event proposal types (EventProposal, ValidationResult)

Moved from wal.py (Event) and event_gate.py (schemas, validation types).
This extraction makes the event model explicit and independently importable.
"""
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# Event Type Registry
# =============================================================================

ALLOWED_EVENT_TYPES: set[str] = {
    "memory_store",
    "memory_access",
    "memory_archive",
    "memory_purge",
    "policy_update",
    "curriculum_task_create",
    "curriculum_task_complete",
    "failure_record",
}

EVENT_SCHEMAS: Dict[str, List[str]] = {
    "memory_store": ["content", "tier"],
    "memory_access": [],
    "memory_archive": ["reason"],
    "memory_purge": [],
    "policy_update": ["policy_weights", "reason"],
    "curriculum_task_create": ["task_id", "difficulty", "family"],
    "curriculum_task_complete": ["task_id", "reward", "success"],
    "failure_record": ["failure_type", "context", "proposed_fix"],
}

FORBIDDEN_FIELDS: list[str] = [
    "state",
    "timestamp",
    "replay_hash",
    "_coaccess",
    "_access_history",
]


# =============================================================================
# Core Event
# =============================================================================

@dataclass  # NOT frozen — replay_hash is set after construction (by WAL.append)
class MCREvent:
    """
    Immutable event record for MCR's event-sourced memory runtime.

    Fields:
        event_id:          Unique identifier (UUID). Engine assigns this.
        event_type:        Which kind of event this is (memory_store, etc.)
        tick:              Monotonically increasing tick assigned by Engine.
        memory_id:         Optional memory identifier for memory operations.
        coaccess_group_id: UUID grouping simultaneous accesses.
        payload:           Event-type-specific data dict.
        timestamp:         Wall-clock time at write.
        replay_hash:      SHA-256 integrity hash computed at write time.
    """
    event_id: str
    event_type: str
    tick: int
    memory_id: Optional[str]
    coaccess_group_id: str
    payload: dict
    timestamp: float
    replay_hash: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict with underscore-prefixed event_type for JSONL storage."""
        d = asdict(self)
        d['_event_type'] = d.pop('event_type')
        return d

    @staticmethod
    def from_dict(d: dict) -> 'MCREvent':
        """Deserialize from dict, restoring event_type from _event_type key."""
        d = dict(d)  # copy to avoid mutating original
        d['event_type'] = d.pop('_event_type')
        return MCREvent(**d)

    def _compute_replay_hash(self) -> str:
        """
        Compute integrity hash excluding replay_hash itself.
        This is written at append time and validated at load time.
        Detects post-write corruption: bit flips, truncation, replay attacks.
        """
        d = self.to_dict()
        d.pop('replay_hash', None)
        # sorted keys for deterministic serialization
        serialized = json.dumps(d, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def compute_replay_hash(self) -> str:
        """Backward-compat alias for _compute_replay_hash()."""
        return self._compute_replay_hash()

    def validate_replay_hash(self) -> bool:
        """
        Validate stored replay_hash against recomputed hash.
        Returns True if valid, False if missing or mismatched.
        """
        if not self.replay_hash:
            return False
        return self.replay_hash == self.compute_replay_hash()

    def equals(self, other: 'MCREvent') -> bool:
        """Content equality excluding replay_hash (which is write-time specific)."""
        return (
            self.event_id == other.event_id
            and self.event_type == other.event_type
            and self.tick == other.tick
            and self.memory_id == other.memory_id
            and self.coaccess_group_id == other.coaccess_group_id
            and self.payload == other.payload
            and abs(self.timestamp - other.timestamp) < 1e-6
        )


# =============================================================================
# Backward-compatibility alias
# =============================================================================

# Old code imported Event from wal.py. Keep alias here so old imports still work
# after the migration, without circular import issues in wal.py.
Event = MCREvent


# =============================================================================
# Hermes Bridge Types (moved from event_gate.py)
# =============================================================================

@dataclass
class EventProposal:
    """LLM output format — unvalidated proposal from LLM."""
    event_type: str
    tick: int
    memory_id: Optional[str]
    coaccess_group_id: str
    payload: Dict[str, Any]
    justification: str = ""


@dataclass
class ValidationResult:
    """Result of EventGate.validate()."""
    accepted: bool
    reason: str
    event: Optional[Any] = None  # Set to MCREvent on acceptance