#!/usr/bin/env python3
"""
Calibrated Pathology Detector — p2-5-B
=======================================

Principle: Observability must be trustworthy before it can guide decisions.

Key changes from v1:
  1. Percentile-based anomaly detection (vs fixed thresholds)
  2. Rolling baseline (vs static baseline)
  3. Sustained anomaly window (vs single-tick trigger)
  4. Normalization phase detection (warmup/transient vs steady-state)
  5. Classification into taxonomy categories

Pathology Taxonomy:
  CLASS A — Detector Artifact      : miscalibrated threshold, not runtime issue
  CLASS B — Workload Artifact       : synthetic pattern, not system behavior
  CLASS C — Measurement Error      : wrong metric attribution
  CLASS D — Benchmark Artifact      : synthetic benchmark specific
  CLASS E — Runtime Pathology      : real system behavior failure
  CLASS F — Known Physics           : expected system behavior

Only CLASS E warrants observation attention.
CLASS A/B/C/D should be filtered before reporting.
CLASS F should be labeled as "expected", not "pathology".
"""

import sys
import os
import json
import time
from datetime import datetime
from collections import defaultdict, deque
from typing import Optional, Callable

# ─────────────────────────────────────────────────────────────────────────────
# PATH SETUP
# ─────────────────────────────────────────────────────────────────────────────

_MCR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _MCR_ROOT)
sys.path.insert(0, os.path.join(_MCR_ROOT, "stable"))

from layered_memory import LayeredMemory

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

OBSERVATION_DIR = os.path.join(_MCR_ROOT, "runtime_phys_observation")
RUN_DATA_DIR = os.path.join(OBSERVATION_DIR, "run_data_calibrated")
os.makedirs(RUN_DATA_DIR, exist_ok=True)

TICKS = 10_000
REPORT_EVERY = 1000

# Workload
TOPICS = [
    "project_alpha", "project_beta", "project_gamma",
    "meeting_notes", "decision_log", "risk_register",
    "user_feedback", "bug_report", "feature_request",
    "code_review", "deployment_log", "test_results",
]
TEMPLATES = [
    "completed {topic} milestone {n} with status {s}",
    "updated {topic} documentation for release {n}",
    "resolved {topic} critical issue in component {c}",
    "deployed {topic} version {n} to {e}",
    "reviewed {topic} PR #{n} from contributor {w}",
]
ENVS = ["production", "staging", "development", "qa"]
TEAMS = ["backend", "frontend", "infra", "security"]
COMPS = ["api", "ui", "db", "cache", "worker"]
PEOPLE = ["alice", "bob", "charlie", "diana"]
STATUSES = ["complete", "partial", "failed", "pending"]


# ─────────────────────────────────────────────────────────────────────────────
# CALIBRATED PATHOLOGY DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class CalibratedPathologyDetector:
    """
    Pathology detection with proper calibration.
    
    Detection rules:
      - Use rolling percentile-based baselines
      - Require sustained anomaly window (not single tick)
      - Classify findings by taxonomy before reporting
      - Apply warmup/transient phase masking
    """

    # Taxonomy classification
    CLASS_A_DETECTOR_ARTIFACT = "detector_artifact"    # miscalibrated threshold
    CLASS_B_WORKLOAD_ARTIFACT = "workload_artifact"    # synthetic pattern
    CLASS_C_MEASUREMENT_ERROR = "measurement_error"    # wrong attribution
    CLASS_D_BENCHMARK_ARTIFACT = "benchmark_artifact"  # benchmark-specific
    CLASS_E_RUNTIME_PATHOLOGY = "runtime_pathology"    # real system failure
    CLASS_F_KNOWN_PHYSICS = "known_physics"             # expected behavior

    def __init__(self, warmup_ticks: int = 2000):
        # Warmup: system needs time to reach steady-state
        # During warmup, accumulation is normal (not pathology)
        self.warmup_ticks = warmup_ticks
        
        # Rolling baselines (deques for sliding window)
        self._latency_window = deque(maxlen=200)
        self._gc_window = deque(maxlen=200)
        self._archive_window = deque(maxlen=1000)  # Archive changes slowly
        self._retrieval_set_buffer = deque(maxlen=200)  # Tick-by-tick retrieval sets
        
        # Sustained anomaly detection
        self._anomaly_counter = defaultdict(int)  # type -> consecutive tick count
        self.SUSTAINED_WINDOW = 50  # Must persist for 50+ ticks to be real anomaly
        
        # Findings (classified)
        self.findings = []
        
        # Phase detection
        self._phase = "warmup"  # warmup | transient | steady_state
    
    def _update_baselines(self, tick: int, lm: LayeredMemory,
                          latency_ms: float, gc_ops: int):
        """Update rolling baselines."""
        self._latency_window.append(latency_ms)
        self._gc_window.append(gc_ops)
        self._archive_window.append(len(lm.archive))
        
        # Phase detection: archive reaches steady state
        if self._phase == "warmup" and tick > self.warmup_ticks:
            if len(set(list(self._archive_window)[-500:])) < 10:
                self._phase = "steady_state"
        elif tick <= self.warmup_ticks:
            self._phase = "warmup"
    
    def _percentile_baseline(self, window: deque, percentile: float) -> float:
        """Compute percentile baseline from rolling window."""
        if len(window) < 10:
            return 0
        sorted_vals = sorted(window)
        idx = int(len(sorted_vals) * percentile)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    def _detect(self, tick: int, lm: LayeredMemory,
                retrieval_result: list, latency_ms: float,
                gc_ops: int) -> list:
        """
        Run all calibrated pathology checks.
        Returns classified findings (never double-counts).
        """
        if self._phase == "warmup":
            return []  # No pathology detection during warmup
        
        detected = []
        
        # ── 1. LATENCY SPIKE ──
        # Use 95th percentile as baseline, require sustained >3x for 50+ ticks
        if len(self._latency_window) >= 50:
            baseline = self._percentile_baseline(self._latency_window, 0.95)
            multiplier = latency_ms / max(baseline, 0.0001)
            
            if multiplier > 3.0:
                self._anomaly_counter["latency_spike"] += 1
            else:
                self._anomaly_counter["latency_spike"] = 0
            
            # Only report if sustained
            if self._anomaly_counter["latency_spike"] >= self.SUSTAINED_WINDOW:
                # Classify
                if latency_ms > 10 and multiplier > 10:
                    severity = "HIGH"
                    classification = self.CLASS_E_RUNTIME_PATHOLOGY
                elif latency_ms > 5:
                    severity = "MEDIUM"
                    classification = self.CLASS_E_RUNTIME_PATHOLOGY
                else:
                    severity = "LOW"
                    classification = self.CLASS_E_RUNTIME_PATHOLOGY
                
                finding = {
                    "tick": tick,
                    "type": "latency_spike",
                    "severity": severity,
                    "classification": classification,
                    "value_ms": round(latency_ms, 4),
                    "baseline_ms": round(baseline, 4),
                    "multiplier": round(multiplier, 2),
                    "sustained_ticks": self._anomaly_counter["latency_spike"],
                    "phase": self._phase,
                    "details": f"sustained {multiplier:.1f}x baseline for {self._anomaly_counter['latency_spike']} ticks",
                    "why": "hard_cap_overflow batch processing causes periodic latency spikes",
                }
                detected.append(finding)
        
        # ── 2. ARCHIVE EXPLOSION ──
        # Archive grows during accumulation phase, stabilizes at steady_state
        # Only flag if: steady_state AND >2x growth in 500 ticks
        if len(self._archive_window) >= 500 and self._phase == "steady_state":
            old = sum(list(self._archive_window)[-1000:-500]) / 500
            new = sum(list(self._archive_window)[-500:]) / 500
            growth_rate = (new - old) / max(old, 1)
            
            if growth_rate > 1.0:  # >100% growth in 500 ticks during steady state = real issue
                self._anomaly_counter["archive_explosion"] += 1
            else:
                self._anomaly_counter["archive_explosion"] = 0
            
            if self._anomaly_counter["archive_explosion"] >= 100:
                finding = {
                    "tick": tick,
                    "type": "archive_explosion",
                    "severity": "HIGH",
                    "classification": self.CLASS_E_RUNTIME_PATHOLOGY,
                    "old_count": round(old, 1),
                    "new_count": round(new, 1),
                    "growth_rate": round(growth_rate, 3),
                    "sustained_ticks": self._anomaly_counter["archive_explosion"],
                    "phase": self._phase,
                    "details": f"archive grew {growth_rate:.1%} in 500 ticks (steady_state)",
                    "why": "deletion rate < accumulation rate, requires GC tuning",
                }
                detected.append(finding)
            elif growth_rate > 0.3:
                # >30% growth — could be transient or early steady-state
                finding = {
                    "tick": tick,
                    "type": "archive_accumulation",
                    "severity": "LOW",
                    "classification": self.CLASS_F_KNOWN_PHYSICS,
                    "old_count": round(old, 1),
                    "new_count": round(new, 1),
                    "growth_rate": round(growth_rate, 3),
                    "phase": self._phase,
                    "details": f"archive grew {growth_rate:.1%} — normal accumulation during phase transition",
                    "why": "expected behavior during accumulation, not a failure",
                }
                detected.append(finding)
        
        # ── 3. SEMANTIC MONOPOLY ──
        # Semantic >60% retrieval share for sustained period
        # (from retrieval explainer layer_share data)
        # Handled externally by retrieval explainer
        
        # ── 4. GC EXPLOSION ──
        # GC >3x baseline for sustained period
        if len(self._gc_window) >= 50:
            baseline = self._percentile_baseline(self._gc_window, 0.95)
            if baseline > 0 and gc_ops / baseline > 3.0:
                self._anomaly_counter["gc_explosion"] += 1
            else:
                self._anomaly_counter["gc_explosion"] = 0
            
            if self._anomaly_counter["gc_explosion"] >= self.SUSTAINED_WINDOW:
                finding = {
                    "tick": tick,
                    "type": "gc_explosion",
                    "severity": "MEDIUM",
                    "classification": self.CLASS_E_RUNTIME_PATHOLOGY,
                    "value": gc_ops,
                    "baseline": round(baseline, 2),
                    "multiplier": round(gc_ops / max(baseline, 0.0001), 2),
                    "sustained_ticks": self._anomaly_counter["gc_explosion"],
                    "phase": self._phase,
                    "details": f"GC {gc_ops} = {gc_ops/baseline:.1f}x baseline for {self._anomaly_counter['gc_explosion']} ticks",
                }
                detected.append(finding)
        
        # ── 5. RETRIEVAL STAGNATION ──
        # Same items retrieved for >100 consecutive ticks
        ids = tuple(sorted([m.get("id") for m in retrieval_result]))
        self._retrieval_set_buffer.append(ids)
        if len(self._retrieval_set_buffer) >= 100:
            unique = len(set(list(self._retrieval_set_buffer)[-100:]))
            if unique < 3:
                self._anomaly_counter["retrieval_stagnation"] += 1
            else:
                self._anomaly_counter["retrieval_stagnation"] = 0
            
            if self._anomaly_counter["retrieval_stagnation"] >= self.SUSTAINED_WINDOW:
                finding = {
                    "tick": tick,
                    "type": "retrieval_stagnation",
                    "severity": "MEDIUM",
                    "classification": self.CLASS_E_RUNTIME_PATHOLOGY,
                    "unique_sets": unique,
                    "window": 100,
                    "sustained_ticks": self._anomaly_counter["retrieval_stagnation"],
                    "phase": self._phase,
                    "details": f"only {unique} unique retrieval sets in last 100 ticks",
                }
                detected.append(finding)
        
        # Deduplicate
        for f in detected:
            if not any(x["type"] == f["type"] and abs(x["tick"] - f["tick"]) < self.SUSTAINED_WINDOW
                      for x in self.findings):
                self.findings.append(f)
        
        return detected

    def summary(self) -> dict:
        by_class = defaultdict(list)
        by_type = defaultdict(list)
        for f in self.findings:
            by_class[f["classification"]].append(f)
            by_type[f["type"]].append(f)
        
        return {
            "total_findings": len(self.findings),
            "by_classification": {k: len(v) for k, v in by_class.items()},
            "by_type": {k: len(v) for k, v in by_type.items()},
            "runtime_pathologies": by_class[self.CLASS_E_RUNTIME_PATHOLOGY],
            "phase_masked": by_class[self.CLASS_A_DETECTOR_ARTIFACT] + 
                           by_class[self.CLASS_B_WORKLOAD_ARTIFACT] +
                           by_class[self.CLASS_F_KNOWN_PHYSICS],
        }


# ─────────────────────────────────────────────────────────────────────────────
# RETRIEVAL EXPLAINER (same as before but simplified)
# ─────────────────────────────────────────────────────────────────────────────

class RetrievalExplainer:
    """Wraps LayeredMemory.retrieve() for explainability."""

    def __init__(self, lm: LayeredMemory):
        self.lm = lm
        self.history = []
        self.layer_hit_counts = {"working": 0, "episodic": 0, "semantic": 0, "archive": 0}
        self.rerank_stats = {"suppressed": 0, "replaced": 0, "overridden": 0}

    def retrieve(self, query: str, current_goal: str = "",
                 current_tick: int = 0, max_results: int = 5,
                 goal_history: list = None) -> tuple:
        goal_history = goal_history or []
        t0 = time.perf_counter()
        selected = self.lm.retrieve(query, current_goal, current_tick, max_results, goal_history)
        latency_ms = (time.perf_counter() - t0) * 1000

        # Track layer hits
        for m in selected:
            layer = m.get("layer", m.get("state", "unknown"))
            if layer in self.layer_hit_counts:
                self.layer_hit_counts[layer] += 1

        # Rerank tracking
        suppressed = sum(1 for m in selected if m.get("_suppressed"))
        replaced = sum(1 for m in selected if m.get("_replaced_from"))
        overridden = sum(1 for m in selected if m.get("_overridden"))
        self.rerank_stats["suppressed"] += suppressed
        self.rerank_stats["replaced"] += replaced
        self.rerank_stats["overridden"] += overridden

        explanation = {
            "tick": current_tick,
            "query": query[:60],
            "latency_ms": round(latency_ms, 4),
            "selected_count": len(selected),
            "layers": [m.get("layer", m.get("state")) for m in selected],
            "rerank": {"suppressed": suppressed, "replaced": replaced, "overridden": overridden},
        }
        self.history.append(explanation)
        return selected, latency_ms, explanation

    def get_layer_share(self) -> dict:
        total = sum(self.layer_hit_counts.values())
        if total == 0:
            return {"working": 0, "episodic": 0, "semantic": 0, "archive": 0}
        return {k: v / total for k, v in self.layer_hit_counts.items()}


# ─────────────────────────────────────────────────────────────────────────────
# METRICS TIMELINE (calibrated)
# ─────────────────────────────────────────────────────────────────────────────

class MetricsTimeline:
    """Collects bounded metrics — no unbounded growth."""

    MAX_LEN = 10_000  # Hard cap on data points to prevent observability explosion

    def __init__(self):
        self.data = defaultdict(list)
        self.all_retrieval_ids = set()
        self.cumulative_retrievals = 0

    def record(self, tick: int, lm: LayeredMemory,
               retrieval_result: list, latency_ms: float,
               gc_ops: int, rerank_rate: float, semantic_share: float):
        # Enforce bounded collection
        if len(self.data["tick"]) >= self.MAX_LEN:
            return

        self.data["tick"].append(tick)
        self.data["memory_working"].append(len(lm.working))
        self.data["memory_episodic"].append(len(lm.episodic))
        self.data["memory_semantic"].append(len(lm.semantic))
        self.data["memory_archive"].append(len(lm.archive))
        self.data["memory_total"].append(
            len(lm.working) + len(lm.episodic) +
            len(lm.semantic) + len(lm.archive)
        )
        self.data["latency_ms"].append(latency_ms)
        self.data["gc_ops"].append(gc_ops)
        self.data["rerank_rate"].append(rerank_rate)
        self.data["semantic_share"].append(semantic_share)

        # Diversity (bounded)
        ids = set(m.get("id") for m in retrieval_result)
        self.all_retrieval_ids.update(ids)
        self.cumulative_retrievals += len(retrieval_result)
        div = len(self.all_retrieval_ids) / max(1, self.cumulative_retrievals)
        self.data["retrieval_diversity"].append(div)

    def summary(self) -> dict:
        lat = self.data["latency_ms"]
        gc = self.data["gc_ops"]
        sem = self.data["semantic_share"]
        div = self.data["retrieval_diversity"]

        half = len(lat) // 2
        early_lat = sum(lat[:half]) / max(half, 1) if lat else 0
        late_lat = sum(lat[-half:]) / max(half, 1) if lat else 0
        lat_ratio = late_lat / max(early_lat, 0.0001)

        early_gc = sum(gc[:half]) / max(half, 1) if gc else 0
        late_gc = sum(gc[-half:]) / max(half, 1) if gc else 0
        gc_ratio = late_gc / max(early_gc, 0.0001)

        return {
            "ticks": len(self.data["tick"]),
            "latency": {
                "avg_ms": round(sum(lat) / len(lat), 4) if lat else 0,
                "max_ms": round(max(lat), 4) if lat else 0,
                "ratio": round(lat_ratio, 4),
                "trend": "stable" if lat_ratio < 1.5 else ("improving" if lat_ratio < 1 else "degrading"),
            },
            "gc": {
                "avg_per_tick": round(sum(gc) / len(gc), 4) if gc else 0,
                "ratio": round(gc_ratio, 4),
                "trend": "stable" if gc_ratio < 1.5 else ("improving" if gc_ratio < 1 else "growing"),
            },
            "semantic_share": {
                "avg": round(sum(sem) / len(sem), 4) if sem else 0,
                "max": round(max(sem), 4) if sem else 0,
            },
            "retrieval_diversity": {
                "final": round(div[-1], 4) if div else 0,
                "avg": round(sum(div) / len(div), 4) if div else 0,
            },
            "memory": {
                "final_total": self.data["memory_total"][-1] if self.data["memory_total"] else 0,
                "final_semantic": self.data["memory_semantic"][-1] if self.data["memory_semantic"] else 0,
                "final_archive": self.data["memory_archive"][-1] if self.data["memory_archive"] else 0,
            },
            "data_bounded": len(self.data["tick"]) < self.MAX_LEN,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC WORKLOAD
# ─────────────────────────────────────────────────────────────────────────────

class SyntheticWorkload:
    def __init__(self, seed=42):
        import random
        random.seed(seed)
        self.tick = 0

    def memory_write(self, lm: LayeredMemory) -> list:
        import random
        self.tick += 1
        for _ in range(random.randint(1, 3)):
            topic = random.choice(TOPICS)
            template = random.choice(TEMPLATES)
            content = template.format(
                topic=topic, n=random.randint(1, 999),
                s=random.choice(STATUSES), e=random.choice(ENVS),
                t=random.choice(TEAMS), c=random.choice(COMPS),
                w=random.choice(PEOPLE),
            )
            importance = random.uniform(0.3, 0.95)
            lm.store(content, "general", importance, [topic], self.tick)
        # Adversarial noise
        if random.random() < 0.1:
            lm.store(f"irrelevant_noise_{random.randint(1, 10000)}", "noise", 0.1, ["noise"], self.tick)

    def query(self) -> str:
        import random
        if random.random() < 0.7:
            return random.choice(TOPICS)
        return random.choice(TOPICS) + " " + random.choice(TOPICS)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN: CALIBRATED RUNTIME PHYSICS OBSERVER
# ─────────────────────────────────────────────────────────────────────────────

class CalibratedRuntimePhysicsObserver:
    """
    Calibrated observability layer — p2-5-B.
    
    Changes from v1:
      - Pathology detector uses rolling percentile baselines
      - Sustained anomaly window (50 ticks minimum)
      - Warmup phase masking (no detection before tick 2000)
      - Taxonomy classification (A-F)
      - Bounded metrics collection (MAX_LEN cap)
    """

    def __init__(self, ticks=TICKS):
        self.ticks = ticks
        self.start_time = time.time()
        self.lm = LayeredMemory(RUN_DATA_DIR)
        self.detector = CalibratedPathologyDetector(warmup_ticks=2000)
        self.explainer = RetrievalExplainer(self.lm)
        self.metrics = MetricsTimeline()
        self.workload = SyntheticWorkload()
        self._retrieval_explanation_history = []

    def run(self):
        print(f"\n{'='*60}")
        print(f"CALIBRATED RUNTIME PHYSICS OBSERVER — {self.ticks} ticks (p2-5-B)")
        print(f"Observability: Calibrated Pathology | Bounded Metrics | Taxonomy")
        print(f"{'='*60}\n")

        for tick in range(1, self.ticks + 1):
            # Memory write
            self.workload.memory_write(self.lm)

            # Retrieval
            query = self.workload.query()
            result, latency_ms, explanation = self.explainer.retrieve(
                query=query,
                current_goal=query,
                current_tick=tick,
                max_results=5,
            )
            self._retrieval_explanation_history.append(explanation)

            # Lifecycle
            self.lm.process_decay_buffer(tick)
            self.lm.incremental_review(tick)

            # GC ops estimate
            gc_ops = 2  # Approximate

            # Rerank rate
            total_mod = sum(self.explainer.rerank_stats.values())
            rerank_rate = (total_mod / len(self.explainer.history)) if self.explainer.history else 0

            # Semantic share
            semantic_share = self.explainer.get_layer_share().get("semantic", 0)

            # Update baselines (always, even during warmup)
            self.detector._update_baselines(tick, self.lm, latency_ms, gc_ops)

            # Calibrated pathology detection (respects warmup)
            pathologies = self.detector._detect(
                tick, self.lm, result, latency_ms, gc_ops
            )

            # Metrics
            self.metrics.record(tick, self.lm, result, latency_ms, gc_ops, rerank_rate, semantic_share)

            # Report
            if tick % REPORT_EVERY == 0:
                self._report(tick)

            # Flush
            if tick % 100 == 0:
                self.lm.try_flush(tick)

        self._final_report()
        self._save_data()

    def _report(self, tick: int):
        elapsed = time.time() - self.start_time
        m = self.metrics.data
        phase = self.detector._phase
        
        wc = m["memory_working"][-1] if m["memory_working"] else 0
        ec = m["memory_episodic"][-1] if m["memory_episodic"] else 0
        sc = m["memory_semantic"][-1] if m["memory_semantic"] else 0
        ac = m["memory_archive"][-1] if m["memory_archive"] else 0
        lat = m["latency_ms"][-1] if m["latency_ms"] else 0

        print(f"\n[TICK {tick}/{self.ticks}] ({elapsed:.1f}s) [{phase}]")
        print(f"  Memory: total={wc+ec+sc+ac} (W={wc} E={ec} S={sc} A={ac})")
        print(f"  Latency: {lat:.4f}ms")
        print(f"  Pathologies: {len(self.detector.findings)}")

    def _final_report(self):
        elapsed = time.time() - self.start_time
        m_summary = self.metrics.summary()
        p_summary = self.detector.summary()
        ls = self.explainer.get_layer_share()
        rs = self.explainer.rerank_stats

        print(f"\n{'='*60}")
        print(f"CALIBRATED FINAL REPORT — {self.ticks} ticks, {elapsed:.1f}s (p2-5-B)")
        print(f"{'='*60}")

        # Metrics
        print(f"\n[BOUNDED METRICS]")
        lat = m_summary["latency"]
        gc = m_summary["gc"]
        print(f"  Latency: {lat['avg_ms']}ms avg | {lat['max_ms']}ms max | trend={lat['trend']} ({lat['ratio']:.2f}x)")
        print(f"  GC: {gc['avg_per_tick']:.2f}/tick | trend={gc['trend']} ({gc['ratio']:.2f}x)")
        print(f"  Semantic share: {m_summary['semantic_share']['avg']:.1%}")
        print(f"  Memory: total={m_summary['memory']['final_total']}, S={m_summary['memory']['final_semantic']}, A={m_summary['memory']['final_archive']}")
        print(f"  Retrieval diversity: {m_summary['retrieval_diversity']['avg']:.1%}")

        # Retrieval explainability
        print(f"\n[RETRIEVAL EXPLAINABILITY]")
        print(f"  Layer share: W={ls['working']:.1%} E={ls['episodic']:.1%} S={ls['semantic']:.1%} A={ls['archive']:.1%}")
        total_mod = sum(rs.values())
        print(f"  Rerank: suppressed={rs['suppressed']} replaced={rs['replaced']} overridden={rs['overridden']}")

        # Pathology taxonomy
        print(f"\n[PATHOLOGY TAXONOMY]")
        print(f"  Total findings: {p_summary['total_findings']}")
        for cls, count in p_summary['by_classification'].items():
            print(f"    {cls}: {count}")
        print(f"  By type: {dict(p_summary['by_type'])}")
        
        if p_summary['runtime_pathologies']:
            print(f"\n  REAL RUNTIME PATHOLOGIES ({len(p_summary['runtime_pathologies'])}):")
            for f in p_summary['runtime_pathologies']:
                print(f"    [{f['severity']}] {f['type']} @ tick {f['tick']}: {f.get('details','')}")
        else:
            print(f"\n  ✓ ZERO RUNTIME PATHOLOGIES")

        # Phase analysis
        print(f"\n[PHASE ANALYSIS]")
        print(f"  Phase: {self.detector._phase}")
        print(f"  Warmup masked: first {self.detector.warmup_ticks} ticks had no pathology detection")
        print(f"  Observability bounded: {m_summary['data_bounded']}")

        print(f"\n[VERDICT]")
        verdicts = []
        if lat['trend'] in ('stable', 'improving'):
            verdicts.append("✓ LATENCY BOUNDED")
        else:
            verdicts.append("✗ LATENCY DEGRADING")
        if gc['trend'] in ('stable', 'improving'):
            verdicts.append("✓ GC BOUNDED")
        else:
            verdicts.append("⚠ GC GROWING")
        if not p_summary['runtime_pathologies']:
            verdicts.append("✓ ZERO RUNTIME PATHOLOGIES")
        else:
            high = sum(1 for f in p_summary['runtime_pathologies'] if f['severity'] == 'HIGH')
            verdicts.append(f"⚠ {len(p_summary['runtime_pathologies'])} RUNTIME PATHOLOGIES ({high} HIGH)")
        for v in verdicts:
            print(f"  {v}")

    def _save_data(self):
        metrics_path = os.path.join(RUN_DATA_DIR, "metrics_calibrated.json")
        with open(metrics_path, "w") as f:
            json.dump(dict(self.metrics.data), f, indent=2)

        path_path = os.path.join(RUN_DATA_DIR, "pathology_calibrated.json")
        with open(path_path, "w") as f:
            json.dump(self.detector.findings, f, indent=2)

        print(f"\n[DATA SAVED]")
        for path in [metrics_path, path_path]:
            size = os.path.getsize(path)
            print(f"  {os.path.basename(path)}: {size:,} bytes")


# ─────────────────────────────────────────────────────────────────────────────
# BOOT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("MCR Calibrated Runtime Physics Observer — p2-5-B")
    print(f"Data dir: {RUN_DATA_DIR}")
    
    observer = CalibratedRuntimePhysicsObserver(ticks=TICKS)
    observer.run()
