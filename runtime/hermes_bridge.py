"""
Hermes Bridge v0.1
Connects Hermes LLM to MCR event-sourced system.
LLM generates event proposals → EventGate validates → Reducer applies → WAL records
"""
import json
import uuid
import subprocess
import sys
from typing import List, Dict, Any, Optional

from .event_gate import EventProposal, EventGate, ValidationResult
from .engine import MCRRuntimeEngine


class HermesBridge:
    """
    Bridge between Hermes LLM and MCR runtime.
    LLM generates proposals; system executes deterministically.
    """

    def __init__(self, engine: MCRRuntimeEngine):
        self.engine = engine
        self.gate = EventGate()
        self.pending_proposals: List[EventProposal] = []

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
            justification=justification
        )

    def submit_proposal(self, proposal: EventProposal) -> ValidationResult:
        """Submit a single proposal through the gate — all events route through Engine.emit_raw() to preserve tick authority and WAL consistency."""
        result = self.gate.validate(proposal)
        if result.accepted:
            event = self.gate.apply(proposal)
            # Route through emit_raw() so engine owns tick authority while preserving
            # the event identity already constructed by EventGate.apply()
            self.engine.emit_raw(event)
            result.event = event
        return result

    def submit_proposals(self, proposals: List[EventProposal]) -> List[ValidationResult]:
        """Submit multiple proposals, stop on first rejection"""
        results = []
        for p in proposals:
            result = self.submit_proposal(p)
            results.append(result)
        return results

    def llm_to_proposals(self, llm_output: str) -> List[EventProposal]:
        """
        Parse LLM text output into EventProposal list.
        Expected format: JSON array or line-delimited JSON
        """
        proposals = []
        try:
            # try JSON array first
            data = json.loads(llm_output)
            if isinstance(data, dict) and "proposals" in data:
                data = data["proposals"]
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    proposal = EventProposal(
                        event_type=item.get("event_type", ""),
                        tick=item.get("tick", self.engine.tick_count + 1),
                        memory_id=item.get("memory_id"),
                        coaccess_group_id=item.get("coaccess_group_id", str(uuid.uuid4())),
                        payload=item.get("payload", {}),
                        justification=item.get("justification", "")
                    )
                    proposals.append(proposal)
        except json.JSONDecodeError:
            # try line-delimited
            for line in llm_output.strip().split('\n'):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        item = json.loads(line)
                        proposal = EventProposal(
                            event_type=item.get("event_type", ""),
                            tick=item.get("tick", self.engine.tick_count + 1),
                            memory_id=item.get("memory_id"),
                            coaccess_group_id=item.get("coaccess_group_id", str(uuid.uuid4())),
                            payload=item.get("payload", {}),
                            justification=item.get("justification", "")
                        )
                        proposals.append(proposal)
                    except json.JSONDecodeError:
                        continue
        return proposals

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state for LLM context"""
        return {
            "tick": self.engine.state.tick,
            "memory_count": len(self.engine.state.memory),
            "access_history_count": len(self.engine.state.access_history),
            "wal_length": self.engine.wal.len(),
            "memory_items": list(self.engine.state.memory.keys())[:10],
        }
