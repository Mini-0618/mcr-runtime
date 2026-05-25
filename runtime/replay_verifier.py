"""
replay_verifier.py — MCR Replay Verifier (G2 Core)

Provides:
  - replay(initial_state, WAL) → final state
  - verify(runtime_state, initial_state, WAL) → result dict
  - wal_hash(WAL) → deterministic SHA-256 of WAL contents

The core G2 invariant:
    runtime_state == replay(initial_state, WAL)

If this holds, the runtime state is verifiable: it was constructed by
reducing every event in order from the WAL. No hidden mutations, no
state drift, no lost events.

The verifier does NOT mutate its inputs. replay() clones initial_state
before reducing, so multiple replay() calls on the same verifier instance
do not accumulate wal_length.
"""
import hashlib
import json
from .reducer import DeterministicReducer
from .state import SystemState
from .wal import WAL


class ReplayVerifier:
    """G2 replay equivalence verifier."""

    def __init__(self):
        self.reducer = DeterministicReducer()

    def replay(self, initial_state: SystemState, wal: WAL) -> SystemState:
        """Replay WAL from initial_state. Returns new state object."""
        state = initial_state.clone()
        for event in wal.get_all():
            state = self.reducer.reduce(event, state)
        return state

    def wal_hash(self, wal: WAL) -> str:
        """
        Deterministic SHA-256 hash of WAL contents.
        Stable across Python sessions.
        Empty string if WAL is empty.
        """
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
        """
        Verify G2 invariant: runtime_state == replay(initial_state, WAL).

        Returns dict with:
          match: bool
          reason: str (ok | state_mismatch | replay_exception)
          detail: str (field-level divergence info)
          runtime_hash, replay_hash, runtime_tick, replay_tick, etc.
        """
        wal_len = wal.len()
        wal_hash = self.wal_hash(wal)
        try:
            replayed = self.replay(initial_state.clone(), wal)
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
            reasons = []
            if runtime_state.tick != replayed.tick:
                reasons.append(f"tick:{runtime_state.tick}!={replayed.tick}")
            if runtime_state.wal_length != replayed.wal_length:
                reasons.append(f"wal_length:{runtime_state.wal_length}!={replayed.wal_length}")
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