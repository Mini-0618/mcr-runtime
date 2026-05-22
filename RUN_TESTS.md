# Test Runner

## Running Tests

**pytest is NOT installed.** Do NOT use `pytest`.

Run tests with:

```
python3 tests/test_g2_replay.py
python3 tests/test_event_gate.py
```

Run both in sequence before any commit.

## What Each Test Validates

### test_g2_replay.py

G2 Replay Equivalence Test — core correctness invariant:

```
runtime_state == replay(WAL)
```

Verifies the runtime engine state matches what you get by replaying all WAL events from empty initial state. If this ever fails, the engine's state diverged from what WAL would reconstruct — a serious correctness violation.

Also validates:
- WAL tick monotonicity (ticks are strictly 1..N, no gaps, no duplicates)
- WAL length and hash reporting
- G2 hash deterministic with `RANDOM_SEED = 42`

### test_event_gate.py

Three sub-tests covering EventGate and HermesBridge:

**test_event_gate_validation** (tests 1–13):
- Rule 1: unknown event type → reject
- Rule 2: missing required payload fields → reject
- Rule 3: forbidden payload fields (state, timestamp, replay_hash, etc.) → reject
- Rule 4: invalid coaccess_group_id (None, non-UUID string) → reject cleanly (no TypeError crash)
- Rule 5: empty memory_id on memory operations → reject
- Rule 6: None memory_id on memory operations → reject cleanly
- Test 8: coaccess_graph isolation — clone mutation must not leak
- Test 9: WAL skips malformed JSON lines silently
- Tests 10–13: edge cases (noop handlers, payload type guard, snapshot cap)

**test_hermes_bridge**: LLM JSON parsing → proposals → accepted/rejected counts

**test_full_integration**: 3-proposal batch through full pipeline, G2 check

## No Dependencies

Tests use only Python stdlib. No pytest, no unittest, no external packages.
