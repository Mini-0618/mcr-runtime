"""
hermes_bridge.py — MCR Hermes Bridge

Connects Hermes LLM output to MCR event-sourced runtime.

Flow:
  LLM generates event proposals (JSON) → llm_to_proposals() → submit_proposals()
  → EventGate.validate() → Engine.emit_raw() → Reducer.reduce() + WAL.append()

Key invariants:
  1. ALL events go through EventGate.validate() — no bypass
  2. Engine owns tick authority — LLM cannot assign tick values
  3. coaccess_group_id must be provided by LLM (not auto-generated) — gate enforces UUID
  4. Snapshot access_history is capped to MAX_SNAPSHOT_ACCESS_HISTORY

This is a mock/development adapter. It does NOT call real LLM APIs.
"""
import json
import uuid
from typing import Any, Dict, List, Optional

from .engine import MCRRuntimeEngine
from .event_gate import EventGate, EventProposal, ValidationResult


MAX_SNAPSHOT_ACCESS_HISTORY = 20


class HermesBridge:
    """
    Hermes LLM ↔ MCR Runtime adapter.

    LLM generates proposals (JSON text). Bridge parses them into EventProposals,
    validates through EventGate, and routes to Engine for execution.
    """

    MAX_SNAPSHOT_ACCESS_HISTORY = 20  # class attribute for test compatibility

    def __init__(self, engine: MCRRuntimeEngine):
        self.engine = engine
        self.gate = EventGate()

    def create_proposal(
        self,
        event_type: str,
        tick: int,
        memory_id: Optional[str],
        coaccess_group_id: str,
        payload: Dict[str, Any],
        justification: str = ""
    ) -> EventProposal:
        return EventProposal(
            event_type=event_type,
            tick=tick,
            memory_id=memory_id,
            coaccess_group_id=coaccess_group_id,
            payload=payload,
            justification=justification,
        )

    def submit_proposal(self, proposal: EventProposal) -> ValidationResult:
        """
        Submit a single proposal through EventGate.
        All events route through Engine.emit_raw() for tick authority.
        """
        result = self.gate.validate(proposal)
        if result.accepted:
            event = self.gate.apply(proposal)
            self.engine.emit_raw(event)
            result.event = event
        return result

    def submit_proposals(self, proposals: List[EventProposal]) -> List[ValidationResult]:
        """Submit multiple proposals. Returns validation results for each."""
        results = []
        for p in proposals:
            results.append(self.submit_proposal(p))
        return results

    def llm_to_proposals(self, llm_output: str) -> List[EventProposal]:
        """
        Parse LLM text output into EventProposal list.
        Expected format: JSON array or line-delimited JSON.

        LLM constraints (enforced by EventGate):
          - event_type must be in ALLOWED_EVENT_TYPES
          - memory_id is REQUIRED and non-empty for memory operations
          - tick is IGNORED (Engine assigns all ticks)
          - coaccess_group_id must be a valid UUID
          - payload fields must match the schema for that event_type
          - Forbidden payload fields: state, timestamp, replay_hash, _coaccess, _access_history
        """
        proposals = []
        try:
            data = json.loads(llm_output)
            if isinstance(data, dict) and "proposals" in data:
                data = data["proposals"]
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            # Try line-delimited JSON
            data = []
            for line in llm_output.strip().split('\n'):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        for item in data:
            if not isinstance(item, dict):
                continue
            proposal = EventProposal(
                event_type=item.get("event_type", ""),
                tick=0,  # IGNORED — Engine assigns all ticks
                memory_id=item.get("memory_id"),
                coaccess_group_id=item.get("coaccess_group_id", ""),
                payload=item.get("payload", {}),
                justification=item.get("justification", ""),
            )
            proposals.append(proposal)
        return proposals

    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get current state snapshot for LLM context.

        access_history is truncated to MAX_SNAPSHOT_ACCESS_HISTORY entries
        to bound LLM context size. WAL replay is unaffected — snapshot is
        context-only and does not affect engine state.
        """
        access_history = self.engine.state.access_history[-self.MAX_SNAPSHOT_ACCESS_HISTORY:]
        return {
            "tick": self.engine.state.tick,
            "memory_count": len(self.engine.state.memory),
            "access_history_count": len(self.engine.state.access_history),
            "access_history": access_history,
            "memory_items": list(self.engine.state.memory.keys())[:10],
        }