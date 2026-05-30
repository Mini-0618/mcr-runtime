"""
memory_writer.py — Memory module

Persists cognitive loop results to MCR runtime via event-sourced WAL.
Uses the runtime's public API — does NOT modify runtime code.
"""
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

# Add project root to path so we can import runtime
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from runtime import MCRRuntimeEngine


class MemoryWriter:
    """Memory: persists cognitive loop results via MCR runtime events."""

    def __init__(self, wal_path: str = "./.wal/cognitive_os.jsonl"):
        self.engine = MCRRuntimeEngine(wal_path=wal_path)

    def store_reflection(self, reflection: Dict[str, Any], cycle_id: str) -> str:
        """Store a reflection as a memory_store event."""
        memory_id = f"cog_reflection_{cycle_id}"
        content = json.dumps(reflection, sort_keys=True)
        self.engine.emit(
            event_type="memory_store",
            memory_id=memory_id,
            coaccess_group_id=str(uuid.uuid4()),
            payload={"content": content, "tier": "episodic"},
        )
        return memory_id

    def store_action(self, action: Dict[str, Any], cycle_id: str) -> str:
        """Store the selected action as a memory event."""
        memory_id = f"cog_action_{cycle_id}"
        content = json.dumps(action, sort_keys=True)
        self.engine.emit(
            event_type="memory_store",
            memory_id=memory_id,
            coaccess_group_id=str(uuid.uuid4()),
            payload={"content": content, "tier": "working"},
        )
        return memory_id

    def verify_replay(self) -> Dict[str, Any]:
        """Run G2 replay verification on all stored events."""
        from runtime import ReplayVerifier
        verifier = ReplayVerifier()
        return verifier.verify(
            self.engine.get_state(),
            self.engine.initial_state,
            self.engine.get_wal(),
        )

    def get_state(self):
        """Return current runtime state."""
        return self.engine.get_state()

    def get_wal(self):
        """Return WAL instance."""
        return self.engine.get_wal()
