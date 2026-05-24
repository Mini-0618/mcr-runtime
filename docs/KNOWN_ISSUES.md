# Known Issues — MCR v0.9.0

## Production Readiness

- **master branch is not protected**
  Branch protection is not enabled. Direct pushes to master bypass review.

- **No CI/CD pipeline**
  There are no automated tests running on push or PR. Test coverage is manual.

- **No semantic promotion in production**
  The semantic layer requires explicit consolidation trigger (Section 22 violation).
  It has never been activated in benchmark runs.

## Benchmark Limitations

- **5-hour G2 verification is preliminary**
  Longer runs (24h+) are needed for production confidence. Current benchmark
  uses synthetic workload — real agent workloads may reveal different patterns.

- **benchmark is synthetic**
  Workload does not represent a real agent's memory access patterns.
  Results may not generalize to production use.

- **Semantic overhead measured on synthetic data**
  Real agent goals and query distributions will differ. The +0.04ms overhead
  is not validated in production conditions.

## Hermes Bridge

- **Hermes Bridge v0.1 is a minimal integration**
  Only validates and routes events. No real LLM integration yet.
  The mock demo shows the integration shape, not production capability.

- **No production deployment**
  The system has not been deployed in a real agent workload environment.

## Architecture

- **API stability not frozen**
  Interfaces may change in v0.10. Do not build production integrations yet.

- **Single-threaded**
  No concurrent access support. Thread safety is not guaranteed.

## Semantic Layer

- **Semantic promotion threshold is benchmark-tuned**
  The 0.4 threshold was lowered from 0.7 to activate the semantic layer
  for benchmarking. A principled production threshold has not been determined.

- **Tombstone lifecycle G3 not verified**
  Phase VII G3 (ghost items — archive items not removed after purge) is not
  fully verified. Known implementation issue with list.remove() indirect lookup.

## WAL / Storage

- **WAL replay assumes deterministic reducer**
  If the reducer's behavior changes between replay and original run
  (e.g., handler bugs, new event types), G2 verification will fail silently.

- **No compaction**
  WAL grows unbounded. No WAL compaction or cleanup strategy is implemented.