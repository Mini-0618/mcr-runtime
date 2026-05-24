# FAQ

## 1. Is MCR an agent framework?

Not exactly. MCR is a memory/runtime substrate for studying replayable long-running agent state. It is not a complete production agent framework.

## 2. Is MCR AGI?

No. MCR is not AGI and does not claim autonomous general intelligence. It is a research artifact for memory state verification.

## 3. Why does MCR need a replay verifier?

Long-running agents need a way to prove that state can be reconstructed from history. The replay verifier checks whether the WAL can reproduce runtime state.

## 4. Why not just use a normal database?

A database can store data, but MCR is focused on state transition auditability and deterministic replay. The goal is not only storage, but verifying how state was produced.

## 5. What is the difference between minimal_mcr.py and quickstart.py?

examples/minimal_mcr.py is a self-contained concept demo. It is the easiest way to understand the core loop. examples/quickstart.py uses the modular runtime files under
untime/.

## 6. Do I need an API key?

No. The demos do not require an API key.

## 7. Do I need a real LLM?

No. The Hermes bridge demo uses mock LLM-style output to demonstrate proposal parsing and validation.

## 8. Who is this for?

MCR is for developers and researchers interested in long-running agents, memory runtime design, event sourcing, replay verification, and state observability.

## 9. Can I use it in production today?

No. The current project is a research runtime artifact and demo-ready engineering artifact. It is not a production-ready agent framework.

## 10. What is next?

The next work is documentation clarity, external validation, replay verification hardening, and keeping the demo/test path stable.
