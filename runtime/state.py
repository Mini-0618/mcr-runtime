"""
State — Immutable Clone Model
"""
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class SystemState:
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
        new_state = SystemState(
            tick=self.tick,
            memory=copy.deepcopy(self.memory),
            access_history=copy.deepcopy(self.access_history),
            coaccess_graph={k: set(v) for k, v in self.coaccess_graph.items()},
            wal_length=self.wal_length,
            _initial=self._initial
        )
        return new_state

    def equals(self, other: 'SystemState') -> bool:
        if self.tick != other.tick:
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

    def hash(self) -> int:
        h = hash((
            self.tick,
            tuple(sorted(self.memory.keys())),
            len(self.access_history),
            tuple(sorted(self.coaccess_graph.keys()))
        ))
        return h
