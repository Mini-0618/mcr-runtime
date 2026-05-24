# FAQ

## 1. Is MCR an Agent framework?

No. MCR is a memory runtime substrate. It does not handle agent loops, tool calling, or LLM orchestration. It provides bounded-retrieval memory and deterministic state replay for agents built on other frameworks.

## 2. Is MCR AGI?

No. MCR makes no claims toward artificial general intelligence. It is an engineering artifact: a replayable memory runtime with bounded retrieval latency.

## 3. Why do you need a replay verifier?

The replay verifier (G2 kernel) ensures `runtime_state == replay(WAL)`. Without it, you cannot detect state divergence — a crash, a bug, or an injected event could corrupt state silently. G2 provides deterministic, cryptographic proof of state integrity at each checkpoint.

## 4. Why not just use a database?

Databases provide durability, not replayability. A SQL database can store memory items, but it cannot reconstruct the exact state sequence that produced the current state. WAL replay gives you time-travel: inspect state at tick N, replay from any checkpoint, verify crash-recovery correctness.

## 5. What's the difference between minimal_mcr.py and quickstart.py?

| | minimal_mcr.py | quickstart.py |
|--|----------------|---------------|
| Lines | ~200 | ~100 |
| Imports | None (self-contained) | Imports from `runtime/` module |
| Entry point | WAL → Reducer → State → Replay (inline) | Full `MCRRuntimeEngine` modular engine |
| Purpose | Understanding core mechanism | Using the modular runtime library |

Start with `minimal_mcr.py` to understand the concept. Use `quickstart.py` to understand the modular API.

## 6. Do I need an API key?

No. Demos run with pure Python stdlib. No OpenAI key, no Anthropic key, no external service. `hermes_bridge_demo.py` uses a mock LLM response.

## 7. Do I need a real LLM?

No. `hermes_bridge_demo.py` demonstrates the bridge with a hardcoded mock response. Real LLM integration requires implementing the `HermesBridge` interface with an actual LLM API call, but this is not required to run or understand the demos.

## 8. Who is this for?

- AI agent framework developers researching bounded-retrieval memory
- Researchers studying event-sourced cognitive architectures
- Engineers building long-running agent services needing crash-recovery
- Students exploring memory lifecycle management in AI systems

## 9. Is it production-ready?

Not yet. Current status is research runtime artifact / demo-ready / regression-protected. Known limitations:

- Semantic layer (theories not yet validated externally)
- No concurrent access support (single-threaded)
- G2 long-run verification is preliminary (5-hour run, needs 24h+ for production confidence)
- No benchmark on real agent workloads (only synthetic)

## 10. What's the next step?

The next milestone is **External User Trial** — collecting the first real feedback from external users who clone and run the demos. Until external validation completes, further core development is paused.

After external trial:
1. Runtime Physics (WAL compaction, tombstone lifecycle)
2. Observability (OpenTelemetry, structured logging)
3. Edge Validation (knowledge graph verification)

## 11. What is the core guarantee?

```
G2 Determinism: runtime_state == replay(WAL)
Bounded Retrieval: O(W+CAP+K) — independent of agent lifetime T
WAL Isolation: WAL is append-only, no in-place mutation after write
```

## 12. How is MCR different from Mem0 / LangChain memory?

| | Mem0 | LangChain | MCR |
|--|------|-----------|-----|
| Latency bound | Query-dependent | Yes, O(W+CAP+K) | Yes, provably bounded |
| Replayable | No | No | Yes (WAL + G2) |
| Tiered memory | Yes | Partial | Yes |
| Event-sourced | No | No | Yes |
| Crash recovery | No | No | Yes (WAL replay) |
| Observable lifecycle | Limited | Limited | Full lifecycle trace |