"""
state_machine.py — MCR Cognitive OS v0.2 State Machine Engine

Replaces the linear cognitive loop with an interruptible state machine.
Supports ASK_OWNER pause points and STOP on high risk.
"""
from typing import Any, Callable, Dict, List, Optional


# All valid states
STATES = [
    "INTAKE", "READ_STATE", "ATTENTION", "SCORE", "POLICY",
    "PLAN", "SELECT_ACTION", "REFLECT", "MEMORY_WRITE", "VERIFY",
    "DONE", "ASK_OWNER", "STOP",
]

# Valid state transitions
TRANSITIONS: Dict[str, List[str]] = {
    "INTAKE": ["READ_STATE"],
    "READ_STATE": ["ATTENTION"],
    "ATTENTION": ["SCORE"],
    "SCORE": ["POLICY"],
    "POLICY": ["PLAN", "ASK_OWNER", "STOP"],
    "PLAN": ["SELECT_ACTION"],
    "SELECT_ACTION": ["REFLECT"],
    "REFLECT": ["MEMORY_WRITE"],
    "MEMORY_WRITE": ["VERIFY"],
    "VERIFY": ["DONE"],
    "DONE": [],
    "ASK_OWNER": ["PLAN", "STOP"],
    "STOP": [],
}


class StateMachineError(Exception):
    pass


class StateMachine:
    """Drives the cognitive loop as a state machine with trace recording."""

    def __init__(self):
        self.state = "INTAKE"
        self.trace: List[Dict[str, Any]] = []
        self._record("INTAKE", "Cycle started")

    def transition(self, next_state: str, reason: str = ""):
        """Transition to next state. Validates against transition table."""
        valid = TRANSITIONS.get(self.state, [])
        if next_state not in valid:
            raise StateMachineError(
                f"Invalid transition: {self.state} → {next_state}. "
                f"Valid: {valid}"
            )
        self.state = next_state
        self._record(next_state, reason)

    def _record(self, state: str, reason: str):
        self.trace.append({
            "state": state,
            "reason": reason,
        })

    def is_terminal(self) -> bool:
        """True if in DONE or STOP."""
        return self.state in ("DONE", "STOP")

    def get_trace(self) -> List[Dict[str, Any]]:
        return list(self.trace)

    def current(self) -> str:
        return self.state
