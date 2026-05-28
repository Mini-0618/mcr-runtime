"""
__init__.py — MCR Runtime Public API

Explicit public API for MCR event-sourced memory runtime.

Backward-compatible re-exports of all public types. Old imports like:
    from runtime import WAL, Event, MCRRuntimeEngine, DeterministicReducer
continue to work without modification.

New recommended imports (using events.py names):
    from runtime import MCRRuntimeEngine
    from runtime.events import MCREvent, EventProposal, ValidationResult

Module structure (v0.10):
    events.py          — Event model, schemas, event types (NEW canonical home)
    wal.py            — Append-only WAL with replay_hash integrity
    state.py          — Immutable-clone runtime state + deterministic SHA-256 hash
    reducer.py        — Pure reducer with typed event handlers
    engine.py         — Runtime engine with tick authority
    event_gate.py     — Validation boundary (8 rules)
    hermes_bridge.py  — Hermes LLM ↔ MCR adapter
    replay_verifier.py — G2 invariant verifier
"""
from .events import (
    ALLOWED_EVENT_TYPES,
    EVENT_SCHEMAS,
    MCREvent,
    Event,
    EventProposal,
    ValidationResult,
)
from .wal import WAL
from .state import SystemState
from .reducer import DeterministicReducer
from .engine import MCRRuntimeEngine
from .event_gate import EventGate
from .hermes_bridge import HermesBridge
from .replay_verifier import ReplayVerifier
from .memory_index import MemoryIndex
from .memory_retriever import MemoryRetriever

__all__ = [
    # events
    'ALLOWED_EVENT_TYPES',
    'EVENT_SCHEMAS',
    'MCREvent',
    'Event',           # backward-compat alias for MCREvent
    'EventProposal',
    'ValidationResult',
    # core
    'WAL',
    'SystemState',
    'DeterministicReducer',
    'MCRRuntimeEngine',
    'EventGate',
    'HermesBridge',
    'ReplayVerifier',
    # memory retrieval
    'MemoryIndex',
    'MemoryRetriever',
]