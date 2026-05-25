# MCR Core Rewrite Plan v0.10

**Date:** 2026-05-25
**Branch:** rewrite/core-v2-candidate

## Why Rewrite

The v0.9.7 runtime is functionally solid, but module structure is unclear:
1. Event model embedded in wal.py
2. No dedicated events.py module
3. Package namespace is runtime (potential stdlib conflict)
4. Public API not explicit

## Module Design

```
runtime/
  __init__.py          - Explicit public API re-exports
  events.py            - MCREvent model, schemas, types (NEW)
  wal.py               - WAL append-only with replay_hash (CLEANED)
  state.py             - SystemState immutable-clone (UNCHANGED)
  reducer.py           - Pure reducer (UNCHANGED)
  engine.py            - Tick authority orchestration (MINOR CLEANUP)
  event_gate.py        - 8 validation rules (MINOR CLEANUP)
  hermes_bridge.py     - LLM adapter (MINOR CLEANUP)
  replay_verifier.py   - G2 verification (UNCHANGED)
```

## Compatibility

All old imports still work via __init__.py re-exports. Examples and tests pass unchanged.

## Verification

All demos pass: minimal_mcr.py library_usage.py quickstart.py replay_verification_demo.py hermes_bridge_demo.py
All pytest tests pass: 12 passed
Editable pip install: passes

## What Did Not Change

- G2 invariant (runtime_state == replay(WAL))
- Append-only WAL semantics
- Deterministic state hash
- Pure reducer
- EventGate 8 rules
- Tick authority
- No external dependencies
