"""
MCR Runtime Engine — tick loop with G2 verification hook
"""
import uuid
import time
from .wal import WAL, Event
from .state import SystemState
from .reducer import DeterministicReducer
from .replay_verifier import ReplayVerifier


class MCRRuntimeEngine:
    def __init__(self, wal_path: str = "/home/minimak/mcr/.wal/events.jsonl"):
        self.wal = WAL(wal_path)
        self.state = SystemState.empty()
        self.initial_state = self.state.clone()
        self.reducer = DeterministicReducer()
        self.verifier = ReplayVerifier()
        self.tick_count = 0
        self.tick_interval = 10  # verify every N ticks; must align with test checkpoints (10,20,30,40,50)

    def emit(self, event_type: str, memory_id: str, coaccess_group_id: str, payload: dict):
        self.tick_count += 1
        tick = self.tick_count
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            tick=tick,
            memory_id=memory_id,
            coaccess_group_id=coaccess_group_id,
            payload=payload,
            timestamp=time.time(),
            replay_hash=""
        )
        # reduce first
        self.state = self.reducer.reduce(event, self.state)
        # then WAL append
        self.wal.append(event)
        return event

    def emit_raw(self, event: Event):
        """
        Process a pre-constructed event through the engine pipeline.
        Engine owns tick authority: sets event.tick to current tick_count.
        Used by HermesBridge to route validated proposals — LLM must not assign ticks.
        """
        self.tick_count += 1
        event.tick = self.tick_count  # engine enforces tick authority; LLM cannot assign
        self.state = self.reducer.reduce(event, self.state)
        self.wal.append(event)
        return event

    def tick(self):
        self.tick_count += 1
        return self.tick_count

    def run(self, num_ticks: int, verify: bool = True):
        for _ in range(num_ticks):
            self.tick()

        if verify and self.tick_count % self.tick_interval == 0:
            result = self.verifier.verify(self.state, self.initial_state, self.wal)
            if not result['match']:
                raise Exception(f"[G2 VIOLATION] tick={self.tick_count} {result}")
            print(f"[G2 OK] tick={self.tick_count} hash={result['runtime_hash']}")
        return self.state

    def get_state(self):
        return self.state

    def get_wal(self):
        return self.wal
