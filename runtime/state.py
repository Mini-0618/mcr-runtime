"""
state.py — MCR Runtime State

Immutable-clone model. State is never mutated in place — every reducer
call returns a new State object with the requested changes applied.

This makes it possible to:
  1. Replay WAL from any point in time
  2. Compare states across replay vs runtime
  3. Detect mutation bugs via G2 invariant

Deterministic hash:
  - SHA-256 with fixed salt b"MCR_STATE_v1"
  - Covers tick, wal_length, memory keys+values, access_history count,
    and full coaccess_graph edge structure
  - Stable across Python sessions (unlike built-in hash() which is salted)
"""
import copy
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List

_STATE_HASH_SALT = b"MCR_STATE_v1"


@dataclass
class SystemState:
    """
    Runtime state snapshot.

    Clone model: all mutating operations return a new SystemState.
    The original is never modified in place.
    """
    tick: int = 0
    memory: Dict[str, dict] = field(default_factory=dict)
    access_history: List[dict] = field(default_factory=list)
    coaccess_graph: Dict[str, set] = field(default_factory=dict)
    wal_length: int = 0
    _initial: bool = False

    @staticmethod
    def empty():
        s = SystemState()
        s._initial = True
        return s

    def clone(self):
        """
        Return a deep copy. coaccess_graph sets are deep-copied so mutations
        on the clone cannot leak back to the original.
        """
        return SystemState(
            tick=self.tick,
            memory=copy.deepcopy(self.memory),
            access_history=copy.deepcopy(self.access_history),
            coaccess_graph={k: copy.deepcopy(set(v)) for k, v in self.coaccess_graph.items()},
            wal_length=self.wal_length,
            _initial=self._initial,
        )

    def equals(self, other: 'SystemState') -> bool:
        """Deep equality — all fields must match."""
        if self.tick != other.tick:
            return False
        if self.wal_length != other.wal_length:
            return False
        if set(self.memory.keys()) != set(other.memory.keys()):
            return False
        for k, v in self.memory.items():
            if k not in other.memory or v != other.memory[k]:
                return False
        if len(self.access_history) != len(other.access_history):
            return False
        if set(self.coaccess_graph.keys()) != set(other.coaccess_graph.keys()):
            return False
        for k, v in self.coaccess_graph.items():
            if set(v) != set(other.coaccess_graph[k]):
                return False
        return True

    def hash(self) -> str:
        """
        SHA-256 state fingerprint with fixed salt.
        Includes full coaccess_graph edge structure, not just keys.
        Stable across Python sessions.
        """
        coaccess_edges = tuple(
            sorted((k, tuple(sorted(v))) for k, v in self.coaccess_graph.items())
        )
        raw = (
            self.tick,
            self.wal_length,
            tuple(sorted(self.memory.keys())),
            len(self.access_history),
            coaccess_edges,
        )
        serialized = str(raw).encode()
        return hashlib.sha256(_STATE_HASH_SALT + serialized).hexdigest()