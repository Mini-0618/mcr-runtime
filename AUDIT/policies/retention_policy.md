# Data Retention Policy v1.0
===========================
HOT (7d):  traces/tick_log/* traces/retrieval_log/*
WARM (30d): traces/gc_log/* traces/semantic_log/* audit/snapshots/*
COLD (180d): benchmark_results/* long_run_reports/*
ARCHIVE (indef): archive/* REGISTRY/versions/*
Exceptions: LOCKS/ REGISTRY/ RUNTIME_POLICY.md snapshots/
*v1.0 FROZEN