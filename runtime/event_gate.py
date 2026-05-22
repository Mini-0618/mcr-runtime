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


def is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


class EventGate:
    """
    Hard boundary: LLM cannot bypass this.
    Only role is validation and conversion.
    """

    def __init__(self):
        self.last_tick = 0
        self._counter = 0

    def validate(self, proposal: EventProposal) -> ValidationResult:
        # Rule 1: event type must be allowed
        if proposal.event_type not in ALLOWED_EVENT_TYPES:
            return ValidationResult(False, f"Unknown event type: {proposal.event_type}")

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

        # Rule 5: tick must be monotonic
        if proposal.tick <= self.last_tick:
            return ValidationResult(False, f"Non-monotonic tick: {proposal.tick} <= {self.last_tick}")

        return ValidationResult(True, "Accepted")

    def apply(self, proposal: EventProposal) -> Any:
        """Convert validated proposal to deterministic event"""
        from .wal import Event
        self._counter += 1
        self.last_tick = proposal.tick

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
