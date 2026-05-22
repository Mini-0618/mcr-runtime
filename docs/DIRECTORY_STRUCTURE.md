# Directory Structure Explanation
=================================

## Why This Structure Exists

MCR is a **research platform**, not a product.
The structure enforces:

1. **Context Isolation** — Research != Operations
2. **Reproducibility** — Every run is traceable
3. **Bounded Complexity** — No feature creep
4. **Evidence Collection** — Observable, not magical

## stable/ — Production Runtime

Only one version lives here: **v0.19f (LKG)**.
Everything in stable has passed benchmark verification.

DO NOT add experimental code to stable/.

## experimental/ — Unverified Research

All hypothesis testing, new governance ideas, benchmark variations.
Never connected to production. Never called "stable."

## archive/ — Historical Frozen Versions

When v0.19f becomes obsolete, it moves here.
Immutable. Used for rollback and comparison.

## observability/ — Evidence Collection

Traces, metrics, pathology catalog.
This is how we know the system is working,
not a way to make the system work better.

## integration/ — Physics Validation

Test integration WITHOUT production risk.
Validate that bounded properties hold in sandbox.

## docs/ — Knowledge Artifact

Architecture decisions, reproducibility manifests,
bounded property verification, long-run reports.
