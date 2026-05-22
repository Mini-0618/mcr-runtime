# MCR Run Reproducibility Manifest
==================================

**Purpose:** Any benchmark run MUST be reproducible from this manifest.
**Owner:** Phase 2.6 | No modification after benchmark starts.

---

## Runtime Identity
```
runtime_version:    v0.19f
stable_tag:        LKG_v0.19f
governance_tag:    semantic_governance_v19f
runtime_hash:      [COMPUTE AFTER RUN]
```

---

## Config Hash
```
config_snapshot:   /home/minimak/mcr/stable/config.py
config_hash:      [COMPUTE AFTER RUN]
```

---

## Benchmark Metadata
```
benchmark_seed:         42
benchmark_tick_count:   [N]
benchmark_start_tick:   [T]
benchmark_command:      python -m pytest benchmarks/ --seed=42 -v
benchmark_duration:     [wall clock]
benchmark_env:          python=3.x.x
```

---

## Snapshot Hash (Pre-Run)
```
pre_run_snapshot:    [PATH]
pre_run_hash:       [SHA256]
post_run_snapshot:   [PATH]
post_run_hash:      [SHA256]
```

---

## Environment
```
python_version:     3.x.x
platform:           Linux-5.x.x-wsl2
working_dir:        /home/minimak/mcr
venv:               [IF USED]
```

---

## Integrity Chain
```
[START] → [CONFIG_HASH] → [SNAPSHOT_HASH] → [BENCHMARK_RUN] → [RESULT_HASH] → [END]

result_hash:        [COMPUTE AFTER RUN]
log_files:          [LIST]
```

---

## Reproduction Steps
```bash
# 1. Checkout exact snapshot
git checkout [SNAPSHOT_HASH]

# 2. Verify config
python -c "import hashlib, config; print(hashlib.sha256(open('config.py','rb').read()).hexdigest())"

# 3. Run benchmark
python -m pytest benchmarks/ --seed=42 -v

# 4. Verify result hash
python -c "import hashlib, json; print(hashlib.sha256(open('results.json','rb').read()).hexdigest())"
```

---

## Change Log
| Date       | Version | Changes | Owner |
|------------|---------|---------|-------|
| YYYY-MM-DD | v0.19f  | Initial | [sig] |

---

## Current Run (ACTIVE / COMPLETED / FAILED)
```
status:             [FILL IN]
run_id:             [UUID]
start_time:         [ISO]
end_time:           [ISO]
tick_count:          [N]
runtime_hash:       [SHA256]
result_hash:        [SHA256]
verdict:            [PASS / FAIL / INCONCLUSIVE]
```

---

## Evidence Files
```
tick_log:           observability/traces/tick_log/YYYYMMDD.jsonl
retrieval_log:      observability/traces/retrieval_log/YYYYMMDD.jsonl
semantic_log:       observability/traces/semantic_log/YYYYMMDD.jsonl
gc_log:             observability/traces/gc_log/YYYYMMDD.jsonl
promotion_log:      observability/traces/promotion_log/YYYYMMDD.jsonl
activation_log:     observability/traces/activation_log/YYYYMMDD.jsonl
```

---

*Append only. Never modify after run starts.*
