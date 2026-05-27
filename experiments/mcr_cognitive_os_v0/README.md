# MCR Cognitive OS v0.1

Local mock experiment for MCR's cognitive architecture layer.

## Modules

| Module | Function |
|--------|----------|
| `state_reader.py` | Perception — reads environment state |
| `attention_filter.py` | Attention — filters tasks by relevance |
| `task_scorer.py` | Brain — scores tasks on priority/risk/cost |
| `goal_manager.py` | Goal — tracks current goals |
| `policy_engine.py` | Policy — enforces boundaries |
| `planner.py` | Planning — generates action plans |
| `action_selector.py` | Action — selects optimal next action |
| `reflection_engine.py` | Reflection — evaluates outcomes |
| `memory_writer.py` | Memory — persists to MCR runtime |
| `run_cognitive_loop.py` | Orchestrator — runs the full loop |

## Run

```bash
python3 experiments/mcr_cognitive_os_v0/run_cognitive_loop.py
```

## Test

```bash
python3 -m pytest -q tests/test_mcr_cognitive_os_v0.py
```
