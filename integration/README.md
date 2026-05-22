# MCR Integration Sandbox
===========================

**Purpose:** Validate integration physics WITHOUT connecting to production runtime.
**Phase:** Phase 2.6 | Integration Scaffolding

---

## What This Is

Sandbox for testing:
- Isolated runtime loop behavior
- Fake agent action injection
- Synthetic retrieval scenarios
- Controlled memory writes
- Bounded property verification

## What This Is NOT

- NOT a production runtime
- NOT connected to autonomous agents
- NOT capable of recursive governance
- NOT for capability testing

## Directory Structure

```
integration/
├── sandbox/           — isolated test runtime
│   └── runtime_sandbox.py   — minimal loop + memory
├── fixtures/          — synthetic test data
│   ├── fake_memory.json
│   ├── synthetic_traces.json
│   └── config_fakes.py
└── test_cases/       — bounded integration tests
    ├── test_bounded_property.py
    ├── test_retrieval_physics.py
    ├── test_memory_isolation.py
    └── test_trace_pipeline.py
```

## Core Principle

> "Verify integration PHYSICS, not capability."

We test:
- Can traces be collected?
- Do logs append without overwrite?
- Does snapshot diff work?
- Are bounded properties preserved?
- Is the pipeline stable over N ticks?

## Running Tests

```bash
cd /home/minimax/mcr
python -m pytest integration/test_cases/ -v

# Or run sandbox directly
python integration/sandbox/runtime_sandbox.py
```

## Banned Patterns

```
❌ production_agent.connect()
❌ autonomous_mutation()
❌ recursive_governance()
❌ live_api_calls()
❌ real_user_data()
```

## Allowed Patterns

```
✅ synthetic memory writes
✅ fake retrieval queries
✅ isolated tick loop
✅ controlled GC operations
✅ trace append verification
```
