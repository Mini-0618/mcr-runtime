"""
ReplayVerifier — G2 Core: verify runtime_state == replay(WAL)
"""
from .reducer import DeterministicReducer
from .state import SystemState
from .wal import Event, WAL


class ReplayVerifier:
    def __init__(self):
        self.reducer = DeterministicReducer()

    def replay(self, initial_state: SystemState, wal: WAL) -> SystemState:
        state = initial_state.clone()
        for event in wal.get_all():
            state = self.reducer.reduce(event, state)
        return state

    def verify(self, runtime_state: SystemState, initial_state: SystemState, wal: WAL) -> dict:
        try:
            replayed = self.replay(initial_state, wal)
        except Exception as exc:
            return {
                'match': False,
                'runtime_hash': runtime_state.hash(),
                'replay_hash': None,
                'replay_error': str(exc),
                'runtime_tick': runtime_state.tick,
                'replay_tick': None,
                'runtime_mem': len(runtime_state.memory),
                'replay_mem': None,
            }
        match = runtime_state.equals(replayed)
        return {
            'match': match,
            'runtime_hash': runtime_state.hash(),
            'replay_hash': replayed.hash(),
            'runtime_tick': runtime_state.tick,
            'replay_tick': replayed.tick,
            'runtime_mem': len(runtime_state.memory),
            'replay_mem': len(replayed.memory),
        }
