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
                'reason': 'replay_exception',
                'detail': str(exc),
                'runtime_hash': runtime_state.hash(),
                'replay_hash': None,
                'replay_tick': None,
                'runtime_tick': runtime_state.tick,
                'runtime_mem': len(runtime_state.memory),
                'replay_mem': None,
            }
        match = runtime_state.equals(replayed)
        if not match:
            # Surface which fields diverge for faster diagnosis.
            reasons = []
            if runtime_state.tick != replayed.tick:
                reasons.append(f"tick:{runtime_state.tick}!={replayed.tick}")
            if set(runtime_state.memory.keys()) != set(replayed.memory.keys()):
                reasons.append(f"memory_keys:{len(runtime_state.memory)}!={len(replayed.memory)}")
            if len(runtime_state.access_history) != len(replayed.access_history):
                reasons.append(f"access_history:{len(runtime_state.access_history)}!={len(replayed.access_history)}")
            if set(runtime_state.coaccess_graph.keys()) != set(replayed.coaccess_graph.keys()):
                reasons.append(f"coaccess_graph_keys:{len(runtime_state.coaccess_graph)}!={len(replayed.coaccess_graph)}")
            reason_str = '; '.join(reasons) if reasons else 'state_hash_mismatch'
            return {
                'match': False,
                'reason': 'state_mismatch',
                'detail': reason_str,
                'runtime_hash': runtime_state.hash(),
                'replay_hash': replayed.hash(),
                'runtime_tick': runtime_state.tick,
                'replay_tick': replayed.tick,
                'runtime_mem': len(runtime_state.memory),
                'replay_mem': len(replayed.memory),
            }
        return {
            'match': True,
            'reason': 'ok',
            'runtime_hash': runtime_state.hash(),
            'replay_hash': replayed.hash(),
            'runtime_tick': runtime_state.tick,
            'replay_tick': replayed.tick,
            'runtime_mem': len(runtime_state.memory),
            'replay_mem': len(replayed.memory),
        }
