"""
engine.py — MCR Runtime Engine

Tick-driven orchestration layer. Owns:
  - Tick authority (Engine assigns all tick values)
  - Event emission (all events go through the Engine)
  - WAL append (via WAL.append())
  - State mutation (via Reducer.reduce())
  - G2 verification hook

Usage:
    engine = MCRRuntimeEngine()
    engine.emit('memory_store', memory_id='m1', coaccess_group_id=str(uuid), payload={...})
    engine.run(num_ticks=10, verify=True)

The Engine does NOT interact with LLM directly. Use HermesBridge for LLM integration.
"""
import time
import uuid
from .events import MCREvent
from .state import SystemState
from .wal import WAL
from .reducer import DeterministicReducer
from .replay_verifier import ReplayVerifier


class MCRRuntimeEngine:
    """
    MCR runtime engine with G2 verification hook.

    All events pass through (WAL-first):
      Event → Engine.emit_raw() → WAL.append() → Reducer.reduce()

    Engine owns tick authority: LLM cannot assign tick values.
    """

    def __init__(self, wal_path: str = "./.wal/events.jsonl", memory_adapter=None):
        self.wal = WAL(wal_path)
        self.reducer = DeterministicReducer(memory_adapter=memory_adapter)
        self.verifier = ReplayVerifier()
        self.tick_count = 0
        self.tick_interval = 10  # verify every N ticks

        # Replay existing WAL to restore state (supports multi-cycle persistence)
        # initial_state stays empty — verifier replays WAL from empty to verify
        self.initial_state = SystemState.empty()
        self.state = self.initial_state.clone()
        for event in self.wal.get_all():
            self.state = self.reducer.reduce(event, self.state)
            if event.tick > self.tick_count:
                self.tick_count = event.tick

    def emit(self, event_type: str, memory_id: str, coaccess_group_id: str, payload: dict) -> MCREvent:
        """Emit a typed memory event."""
        return self._emit(event_type, memory_id, coaccess_group_id, payload)

    def emit_raw(self, event: MCREvent) -> MCREvent:
        """
        Process a pre-constructed event (from HermesBridge via EventGate).
        Engine sets tick to enforce tick authority.
        MCREvent is frozen, so we reconstruct with the assigned tick.
        """
        self.tick_count += 1
        event = MCREvent(
            event_id=event.event_id,
            event_type=event.event_type,
            tick=self.tick_count,
            memory_id=event.memory_id,
            coaccess_group_id=event.coaccess_group_id,
            payload=event.payload,
            timestamp=event.timestamp,
            replay_hash="",
        )
        self.wal.append(event)
        self.state = self.reducer.reduce(event, self.state)
        return event

    def _emit(self, event_type: str, memory_id: str, coaccess_group_id: str, payload: dict) -> MCREvent:
        """Internal emit: assign tick, WAL-first, then reduce."""
        self.tick_count += 1
        event = MCREvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            tick=self.tick_count,
            memory_id=memory_id,
            coaccess_group_id=coaccess_group_id,
            payload=payload,
            timestamp=time.time(),
            replay_hash="",  # computed in WAL.append()
        )
        self.wal.append(event)
        self.state = self.reducer.reduce(event, self.state)
        return event

    def tick(self) -> int:
        """Advance tick counter. Returns new tick value."""
        self.tick_count += 1
        return self.tick_count

    def run(self, num_ticks: int, verify: bool = True):
        """
        Advance tick counter and optionally verify G2 invariant.
        Called by tick-loop integrations (e.g. MCR5hDriver).
        """
        for _ in range(num_ticks):
            self.tick()
        if verify:
            result = self.verifier.verify(self.state, self.initial_state, self.wal)
            if not result['match']:
                raise Exception(f"[G2 VIOLATION] tick={self.tick_count} {result}")
            if self.tick_count % self.tick_interval == 0:
                print(f"[G2 OK] tick={self.tick_count} hash={result['runtime_hash']}")
        return self.state

    def get_state(self) -> SystemState:
        return self.state

    def get_wal(self) -> WAL:
        return self.wal