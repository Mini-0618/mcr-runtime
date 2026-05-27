# MCR Cognitive OS Design

## Architecture

```
Tasks → Perception → Attention → Scoring → Policy → Planning → Action → Execution → Reflection → Memory
```

## Cognitive Cycle

1. **Perception** (state_reader): Load tasks, read current state
2. **Attention** (attention_filter): Filter by urgency and relevance
3. **Scoring** (task_scorer): Score on priority, risk, token cost
4. **Policy** (policy_engine): Check boundaries — block destructive, flag owner-required
5. **Planning** (planner): Rank and order actionable tasks
6. **Action Selection** (action_selector): Pick optimal next_action
7. **Execution**: Simulate action outcome (mock)
8. **Reflection** (reflection_engine): Evaluate if action was good
9. **Memory** (memory_writer): Store experience via MCR runtime events
10. **Verification**: G2 replay verification of all memory events

## Integration with MCR Runtime

- Memory writes go through MCR's event-sourced WAL
- Each cognitive cycle emits `memory_store` events
- Replay verifier validates G2 invariant at end
- No runtime code is modified — we import and use the public API

## Constraints

- No real network access
- No real browser control
- No secret access
- No runtime modification
- All execution is local mock
