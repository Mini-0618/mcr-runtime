"""
ReplayVerifier — G2 Core: verify runtime_state == replay(WAL)
"""
import hashlib
import json
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

    def _wal_hash(self, wal: WAL) -> str:
        """SHA-256 over canonical JSON lines, in order. Empty string if WAL is empty."""
        if wal.len() == 0:
            return ""
        lines = []
        for evt in wal.get_all():
            d = evt.to_dict()
            d.pop('replay_hash', None)
            lines.append(json.dumps(d, sort_keys=True, separators=(',', ':')))
        combined = '|'.join(lines).encode()
        return hashlib.sha256(combined).hexdigest()

    def verify(self, runtime_state: SystemState, initial_state: SystemState, wal: WAL) -> dict:
        # Note: state.hash() returns SHA-256 hex str (was int with per-process salted
        # built-in hash). All hash fields below are now deterministic hex strings.
        wal_len = wal.len()
        wal_hash = self._wal_hash(wal)
        try:
            replayed = self.replay(initial_state, wal)
        except Exception as exc:
            return {
                'match': False,
                'reason': 'replay_exception',
                'detail': str(exc),
                'runtime_hash': runtime_state.hash(),
                'replay_hash': None,
                'runtime_tick': runtime_state.tick,
                'replay_tick': None,
                'runtime_mem': len(runtime_state.memory),
                'replay_mem': None,
                'wal_length': wal_len,
                'wal_hash': wal_hash,
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
                'wal_length': wal_len,
                'wal_hash': wal_hash,
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
            'wal_length': wal_len,
            'wal_hash': wal_hash,
        }
