"""
Event Gate Layer v0.1
LLM → event proposal → validation → deterministic reducer
Hard boundary: LLM cannot mutate state directly
"""
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


ALLOWED_EVENT_TYPES = {
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

FORBIDDEN_FIELDS = [
    "state",
    "timestamp",
    "replay_hash",
    "_coaccess",
    "_access_history",
]


@dataclass
class EventProposal:
    """LLM output format"""
    event_type: str
    tick: int
    memory_id: Optional[str]
    coaccess_group_id: str
    payload: Dict[str, Any]
    justification: str = ""


@dataclass
class ValidationResult:
    accepted: bool
    reason: str
    event: Optional[Any] = None  # Event type, set at runtime


def is_valid_uuid(s) -> bool:
    # Defensively handle None and non-string types before uuid.UUID() call.
    # None can arrive here if LLM provides "coaccess_group_id": null in JSON
    # and bridge passes it through without auto-generating a UUID.
    if s is None:
        return False
    if not isinstance(s, str):
        return False
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class EventGate:
    """
    Hard boundary: LLM cannot bypass this.
    Only role is validation and conversion.
    """

    def __init__(self):
        pass

    def validate(self, proposal: EventProposal) -> ValidationResult:
        # Rule 1: event type must be allowed
        if proposal.event_type not in ALLOWED_EVENT_TYPES:
            return ValidationResult(False, f"Unknown event type: {proposal.event_type}")

        # Rule 7: payload must be a dict, not None or non-dict.
        # Checked early because Rule 2 iterates over payload. If payload is None,
        # "field_name in None" raises TypeError. Must come before Rule 2.
        if not isinstance(proposal.payload, dict):
            return ValidationResult(False, f"payload must be a dict, got {type(proposal.payload).__name__}")

        # Rule 8: payload must not contain fields outside the event's schema.
        # Required fields are enforced by Rule 2. Extraneous fields indicate a malformed
        # proposal (LLM included fields not in schema). Rejecting here keeps WAL clean
        # and prevents the LLM from smuggling constraint-violating fields into state.
        # Reducer already ignores unknown fields, so stripping extras (not rejecting) would
        # also be safe — but rejecting makes the constraint violation explicit for LLM
        # self-correction. Empty payload ({}) is valid for event types with no schema fields.
        schema_fields = set(EVENT_SCHEMAS.get(proposal.event_type, []))
        payload_fields = set(proposal.payload.keys())
        extra_fields = payload_fields - schema_fields
        if extra_fields:
            return ValidationResult(False, f"Unexpected payload fields for {proposal.event_type}: {sorted(extra_fields)}")

        # Rule 2: required fields must be present
        required = EVENT_SCHEMAS.get(proposal.event_type, [])
        for field_name in required:
            if field_name not in proposal.payload:
                return ValidationResult(False, f"Missing required field: {field_name}")

        # Rule 3: forbidden fields must not be present
        for field_name in FORBIDDEN_FIELDS:
            if field_name in proposal.payload:
                return ValidationResult(False, f"Forbidden field: {field_name}")

        # Rule 4: coaccess_group_id must be valid UUID (field, not payload)
        if not is_valid_uuid(proposal.coaccess_group_id):
            return ValidationResult(False, f"Invalid coaccess_group_id: {proposal.coaccess_group_id}")

        # Rule 5: memory_id must be a non-empty string for memory operations.
        # Reducer silently ignores empty memory_id (store does nothing, access
        # returns early), producing a no-op event that still increments wal_length.
        # Catch this at the gate rather than letting state diverge from WAL.
        # Non-string types (int, float, list, etc.) are also rejected — the
        # reducer stores memory_id as-is in WAL and access_history; type
        # inconsistency (int in WAL, str elsewhere) breaks G2 replay.
        MEMORY_OPS = {'memory_store', 'memory_access', 'memory_archive', 'memory_purge'}
        if proposal.event_type in MEMORY_OPS:
            if not isinstance(proposal.memory_id, str) or not proposal.memory_id.strip():
                return ValidationResult(False, f"memory_id must be a non-empty string for {proposal.event_type}, got {type(proposal.memory_id).__name__}")

        # Rule 6: tick must be monotonic — enforced by Engine.emit() which owns tick authority.
        # EventGate.validate() does not track gate-wide tick state (each verifier instance
        # is independent), so monotonicity must be enforced at the Engine layer.

        return ValidationResult(True, "Accepted")

    def apply(self, proposal: EventProposal) -> Any:
        """Convert validated proposal to deterministic event.

        Note: proposal.tick is used as a placeholder here. Engine.emit_raw()
        overwrites event.tick with engine-assigned tick_count to enforce
        LLM-cannot-assign-ticks invariant. proposal.tick may be stale or
        LLM-provided and must not be trusted.
        """
        from .wal import Event

        return Event(
            event_id=str(uuid.uuid4()),
            event_type=proposal.event_type,
            tick=proposal.tick,
            memory_id=proposal.memory_id,
            coaccess_group_id=proposal.coaccess_group_id,
            payload=proposal.payload,
            timestamp=time.time(),
            replay_hash=""
        )

    def process_proposals(self, proposals: List[EventProposal]) -> List[ValidationResult]:
        """Process a batch of proposals, return validation results"""
        results = []
        for p in proposals:
            result = self.validate(p)
            if result.accepted:
                result.event = self.apply(p)
            results.append(result)
        return results
