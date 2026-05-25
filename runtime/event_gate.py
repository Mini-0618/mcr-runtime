"""
event_gate.py — MCR Event Gate

Hard boundary between the outside world (LLM output) and the event-sourced runtime.
Every event from an LLM must pass through EventGate.validate() before reaching
the WAL. There is no bypass path.

Rules (enforced in order):
  1. event_type must be in ALLOWED_EVENT_TYPES
  2. payload must contain all required schema fields for that event_type
  3. payload must NOT contain any FORBIDDEN_FIELDS
  4. coaccess_group_id must be a valid UUID
  5. memory_id must be a non-empty string for memory operations
  6. payload must be a dict (not None, list, or primitive)
  7. payload must not contain fields outside the event's schema
  8. tick is set by Engine (not by LLM) — enforced at Engine.emit_raw()

If any rule fails, the event is REJECTED. A rejected event does NOT modify state
or touch the WAL. The LLM receives a ValidationResult with a rejection reason.
"""
import uuid
from typing import Optional

from .events import (
    ALLOWED_EVENT_TYPES,
    EVENT_SCHEMAS,
    FORBIDDEN_FIELDS,
    MCREvent,
    EventProposal,
    ValidationResult,
)


def is_valid_uuid(s) -> bool:
    """Check if s is a valid UUID string. Handles None safely."""
    if s is None or not isinstance(s, str):
        return False
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


class EventGate:
    """
    Hard boundary: LLM cannot bypass this.
    Only role is validation and proposal→event conversion.
    """

    def validate(self, proposal: EventProposal) -> ValidationResult:
        # Rule 1: event_type in ALLOWED_EVENT_TYPES
        if proposal.event_type not in ALLOWED_EVENT_TYPES:
            return ValidationResult(False, f"Unknown event type: {proposal.event_type}")

        # Rule 6: payload must be a dict (checked before Rule 2 which iterates it)
        if not isinstance(proposal.payload, dict):
            return ValidationResult(False, f"payload must be a dict, got {type(proposal.payload).__name__}")

        # Rule 7: no extraneous payload fields (fields not in schema)
        schema_fields = set(EVENT_SCHEMAS.get(proposal.event_type, []))
        extra_fields = set(proposal.payload.keys()) - schema_fields
        if extra_fields:
            return ValidationResult(False, f"Unexpected payload fields for {proposal.event_type}: {sorted(extra_fields)}")

        # Rule 2: required schema fields must be present
        for field_name in EVENT_SCHEMAS.get(proposal.event_type, []):
            if field_name not in proposal.payload:
                return ValidationResult(False, f"Missing required field: {field_name}")

        # Rule 3: forbidden fields must not be present
        for field_name in FORBIDDEN_FIELDS:
            if field_name in proposal.payload:
                return ValidationResult(False, f"Forbidden field: {field_name}")

        # Rule 4: coaccess_group_id must be a valid UUID
        if not is_valid_uuid(proposal.coaccess_group_id):
            return ValidationResult(False, f"Invalid coaccess_group_id: {proposal.coaccess_group_id}")

        # Rule 5: memory_id must be non-empty string for memory operations
        MEMORY_OPS = {'memory_store', 'memory_access', 'memory_archive', 'memory_purge'}
        if proposal.event_type in MEMORY_OPS:
            if not isinstance(proposal.memory_id, str) or not proposal.memory_id.strip():
                return ValidationResult(
                    False,
                    f"memory_id must be a non-empty string for {proposal.event_type}, got {type(proposal.memory_id).__name__}"
                )

        return ValidationResult(True, "Accepted")

    def apply(self, proposal: EventProposal) -> MCREvent:
        """
        Convert a validated proposal to an MCREvent.
        Note: proposal.tick is ignored — Engine.emit_raw() overwrites it.
        """
        import time
        return MCREvent(
            event_id=str(uuid.uuid4()),
            event_type=proposal.event_type,
            tick=proposal.tick,  # Engine overwrites this
            memory_id=proposal.memory_id,
            coaccess_group_id=proposal.coaccess_group_id,
            payload=proposal.payload,
            timestamp=time.time(),
            replay_hash="",
        )

    def process_proposals(self, proposals):
        """Process a list of proposals. Returns validation results."""
        results = []
        for p in proposals:
            result = self.validate(p)
            if result.accepted:
                result.event = self.apply(p)
            results.append(result)
        return results