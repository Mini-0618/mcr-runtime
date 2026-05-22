#!/usr/bin/env python3
"""
MCR Runtime Physics Observer — Enhanced (Path A: Observability Deep Dive)
============================================================================

OBSERVABILITY LAYER — 不控制系统，只观测。

5个核心模块：
  1. Transition Trace      — promotion/archive/decay reason 分析
  2. Retrieval Explainability — 每次 retrieval 输出命中原因
  3. Runtime Metrics Timeline — latency/memory/gc/semantic ratio curves
  4. Pathology Detector    — 被动检测，不 patch
  5. Tick Snapshot Sampling — 定期保存 memory 快照

Rules:
  - NO new governance layers
  - NO adaptive semantic controllers
  - NO self-modifying retrieval policies
  - Pathology is CATALOGED, not patched
  - GC 1.07x trend 是 physics，不是 bug

LKG: v0.19g — hash: 637a11c907e8a889b909513522dfab8c
"""

import sys
import os
import json
import time
import random
from datetime import datetime
from collections import defaultdict, Counter
from typing import Any, Callable, Optional

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
RUN_DATA_DIR = os.path.join(OBSERVATION_DIR, "run_data")
os.makedirs(RUN_DATA_DIR, exist_ok=True)

# Synthetic workload config
TOPICS = [
    "project_alpha", "project_beta", "project_gamma",
    "meeting_notes", "decision_log", "risk_register",
    "user_feedback", "bug_report", "feature_request",
    "code_review", "deployment_log", "test_results",
    "research_notes", "experiment_log", "analysis_report",
]
TEMPLATES = [
    "completed {topic} milestone {n} with status {s}",
    "updated {topic} documentation for release {n}",
    "resolved {topic} critical issue in component {c}",
    "deployed {topic} version {n} to {e}",
    "reviewed {topic} PR #{n} from contributor {w}",
    "analyzed {topic} performance metrics for sprint {n}",
    "planned {topic} roadmap for quarter {q}",
    "fixed {topic} regression in {c} version {n}",
    "discussed {topic} design with team {t}",
    "validated {topic} requirements for customer {c}",
]
ENVS = ["production", "staging", "development", "qa"]
TEAMS = ["backend", "frontend", "infra", "security", "data"]
COMPS = ["api", "ui", "db", "cache", "worker", "gateway"]
PEOPLE = ["alice", "bob", "charlie", "diana", "eve", "frank"]
STATUSES = ["complete", "partial", "failed", "pending"]

# Runtime config
TICKS = 10_000
REPORT_EVERY = 1000
SNAPSHOT_EVERY = 500
RANDOM_SEED = 42

# Pathology thresholds (detection only, NOT intervention)
SEMANTIC_MONOPOLY_THRESHOLD = 0.60   # semantic retrieval share > 60%
ARCHIVE_EXPLOSION_RATE = 0.05        # archive growth > 5% per 1000 ticks
LATENCY_SPIKE_MULTIPLIER = 3.0       # latency > 3x recent avg
RETRIEVAL_STAGNATION_TICKS = 200     # same items retrieved for N ticks
GC_GROWTH_THRESHOLD = 1.5            # GC trend > 1.5x = concerning


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1: TRANSITION TRACE ANALYZER
# Reads existing transitions.jsonl from LayeredMemory
# ─────────────────────────────────────────────────────────────────────────────

class TransitionTrace:
    """
    Analyzes memory state transitions from LayeredMemory's transitions.jsonl.
    
    Answers:
      - Why was this memory promoted?
      - Why was it archived?
      - What is the most common promotion reason?
      - What is the lifetime distribution?
    """

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.transitions = []
        self.by_reason = Counter()
        self.by_state_pair = Counter()
        self.memory_lifetimes = defaultdict(list)
        self._load()
    
    def _load(self):
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    self.transitions.append(entry)
                    self.by_reason[entry.get("reason", "unknown")] += 1
                    pair = f"{entry.get('from', '')}→{entry.get('to', '')}"
                    self.by_state_pair[pair] += 1
                    
                    # Track lifetime per memory
                    mid = entry.get("memory_id")
                    tick = entry.get("tick", 0)
                    if mid:
                        self.memory_lifetimes[mid].append(tick)
                except json.JSONDecodeError:
                    continue
    
    def reload(self):
        """Re-load transitions from disk (call after runtime run)."""
        self.transitions = []
        self.by_reason = Counter()
        self.by_state_pair = Counter()
        self.memory_lifetimes = defaultdict(list)
        self._load()
    
    def promotion_reason_histogram(self) -> dict:
        """Returns: {reason: count} for all state promotions."""
        return dict(self.by_reason)
    
    def transition_graph(self) -> dict:
        """Returns: {(from, to): count} for all state transitions."""
        return {(k.split("→")[0], k.split("→")[1]): v 
                for k, v in self.by_state_pair.items()}
    
    def avg_memory_lifetime(self) -> Optional[float]:
        """Average ticks a memory lives before reaching terminal state."""
        lifetimes = []
        for mid, ticks in self.memory_lifetimes.items():
            if len(ticks) >= 2:
                lifetimes.append(ticks[-1] - ticks[0])
        return sum(lifetimes) / len(lifetimes) if lifetimes else None
    
    def summary(self) -> dict:
        return {
            "total_transitions": len(self.transitions),
            "top_promotion_reasons": dict(self.by_reason.most_common(5)),
            "transition_graph": dict(self.by_state_pair.most_common(10)),
            "avg_lifetime": self.avg_memory_lifetime(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2: RETRIEVAL EXPLAINABILITY WRAPPER
# Wraps LayeredMemory.retrieve() to capture per-item scores/reasons
# ─────────────────────────────────────────────────────────────────────────────

class RetrievalExplainer:
    """
    Wraps LayeredMemory retrieve() to output explainable retrieval results.
    
    Each retrieval returns:
      - selected items with scores
      - layer of origin
      - suppression/replacement/override flags
      - score breakdown (importance/recency/goal_relevance/semantic_sim)
    """

    def __init__(self, lm: LayeredMemory):
        self.lm = lm
        self.history = []  # List[RetrievalRecord]
        self.rerank_stats = {"suppressed": 0, "replaced": 0, "overridden": 0}
        self.layer_hit_counts = {"working": 0, "episodic": 0, "semantic": 0, "archive": 0}
    
    def retrieve(self, query: str, current_goal: str = "", 
                 current_tick: int = 0, max_results: int = 5,
                 goal_history: list = None) -> list:
        """
        Retrieve with explainability.
        Returns (selected_items, explanation_dict).
        """
        goal_history = goal_history or []
        
        # Capture state before
        layer_counts_before = {
            "working": len(self.lm.working),
            "episodic": len(self.lm.episodic),
            "semantic": len(self.lm.semantic),
            "archive": len(self.lm.archive),
        }
        
        # Call real retrieve
        start_time = time.perf_counter()
        selected = self.lm.retrieve(query, current_goal, current_tick, 
                                      max_results, goal_history)
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # Build explanation
        items_explained = []
        for m in selected:
            explained = {
                "id": m.get("id"),
                "content": m.get("content", "")[:60],
                "state": m.get("state"),
                "layer": m.get("layer", m.get("state")),
                "importance": m.get("importance"),
                "retrieval_score": m.get("retrieval_score"),
                "goal_relevance": m.get("goal_relevance", 0),
                "access_count": m.get("access_count", 0),
                "last_access_tick": m.get("last_access_tick", 0),
                "suppressed": m.get("_suppressed", False),
                "replaced_from": m.get("_replaced_from"),
                "overridden": m.get("_overridden", False),
                "age_ticks": current_tick - m.get("created_tick", 0),
            }
            
            # Score breakdown
            imp = m.get("importance", 0.5) * 0.25
            last = m.get("last_access_tick", 0)
            age = max(0, current_tick - last)
            rec = max(0.0, 1.0 - age * 0.02) * 0.15
            gr = m.get("goal_relevance", 0) * 0.40
            explained["score_breakdown"] = {
                "importance": round(imp, 4),
                "recency": round(rec, 4),
                "goal_relevance": round(gr, 4),
            }
            
            items_explained.append(explained)
            
            # Track layer hits
            layer = m.get("layer", m.get("state"))
            if layer in self.layer_hit_counts:
                self.layer_hit_counts[layer] += 1
        
        # Suppression/replacement/override counts
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
            "layer_counts_before": layer_counts_before,
            "rerank": {
                "suppressed": suppressed,
                "replaced": replaced,
                "overridden": overridden,
                "total_modified": suppressed + replaced + overridden,
            },
            "items": items_explained,
        }
        
        self.history.append(explanation)
        return selected, explanation
    
    def get_layer_share(self) -> dict:
        """Returns retrieval share by layer (0.0-1.0)."""
        total = sum(self.layer_hit_counts.values())
        if total == 0:
            return {"working": 0, "episodic": 0, "semantic": 0, "archive": 0}
        return {k: v / total for k, v in self.layer_hit_counts.items()}
    
    def get_rerank_rate(self) -> float:
        """Fraction of retrievals that had any rerank modification."""
        if not self.history:
            return 0.0
        total_mod = sum(e["rerank"]["total_modified"] for e in self.history)
        return total_mod / len(self.history)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3: RUNTIME METRICS TIMELINE
# Collects all metrics per tick
# ─────────────────────────────────────────────────────────────────────────────

class MetricsTimeline:
    """
    Collects per-tick metrics for timeline analysis.
    
    Metrics:
      - memory_counts (per layer)
      - latency_ms
      - gc_ops
      - semantic_retrieval_share
      - retrieval_diversity (unique items / total)
      - active_memory_count
      - rerank_rate
    """

    def __init__(self):
        self.data = {
            "tick": [],
            "memory_working": [],
            "memory_episodic": [],
            "memory_semantic": [],
            "memory_archive": [],
            "memory_total": [],
            "latency_ms": [],
            "gc_ops": [],
            "semantic_share": [],
            "retrieval_diversity": [],
            "retrieval_count": [],
            "rerank_rate": [],
        }
        self._retrieval_ids_this_tick = []
        self._all_retrieval_ids = set()
        self._cumulative_retrievals = 0
    
    def record_tick(self, tick: int, lm: LayeredMemory,
                    retrieval_result: list, latency_ms: float,
                    gc_ops: int, rerank_rate: float):
        """Record metrics for one tick."""
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
        self.data["retrieval_count"].append(len(retrieval_result))
        self.data["rerank_rate"].append(rerank_rate)
        
        # Retrieval diversity
        ids = [m.get("id") for m in retrieval_result]
        self._all_retrieval_ids.update(ids)
        self._cumulative_retrievals += len(retrieval_result)
        unique_ratio = len(self._all_retrieval_ids) / max(1, self._cumulative_retrievals)
        self.data["retrieval_diversity"].append(unique_ratio)
    
    def record_semantic_share(self, explainer: RetrievalExplainer):
        """Record semantic retrieval share for this tick."""
        share = explainer.get_layer_share()
        self.data["semantic_share"].append(share.get("semantic", 0))
    
    def get_series(self, name: str) -> list:
        return self.data.get(name, [])
    
    def get_trend(self, name: str, window: int = 1000) -> tuple:
        """Returns (early_avg, late_avg, ratio) for a metric."""
        series = self.data.get(name, [])
        if len(series) < window * 2:
            return None, None, None
        early = sum(series[:window]) / window
        late = sum(series[-window:]) / window
        ratio = late / max(early, 0.0001)
        return early, late, ratio
    
    def summary(self) -> dict:
        lat = self.data["latency_ms"]
        gc = self.data["gc_ops"]
        sem_share = self.data["semantic_share"]
        div = self.data["retrieval_diversity"]
        
        early_lat = sum(lat[:1000]) / min(1000, len(lat))
        late_lat = sum(lat[-1000:]) / min(1000, len(lat))
        lat_ratio = late_lat / max(early_lat, 0.0001)
        
        early_gc = sum(gc[:1000]) / min(1000, len(gc))
        late_gc = sum(gc[-1000:]) / min(1000, len(gc))
        gc_ratio = late_gc / max(early_gc, 0.0001)
        
        return {
            "ticks": len(self.data["tick"]),
            "latency": {
                "avg_ms": round(sum(lat) / len(lat), 4) if lat else 0,
                "max_ms": round(max(lat), 4) if lat else 0,
                "early_avg_ms": round(early_lat, 4),
                "late_avg_ms": round(late_lat, 4),
                "ratio": round(lat_ratio, 4),
            },
            "gc": {
                "avg_per_tick": round(sum(gc) / len(gc), 4) if gc else 0,
                "early_avg": round(early_gc, 4),
                "late_avg": round(late_gc, 4),
                "ratio": round(gc_ratio, 4),
            },
            "semantic_share": {
                "avg": round(sum(sem_share) / len(sem_share), 4) if sem_share else 0,
                "max": round(max(sem_share), 4) if sem_share else 0,
            },
            "retrieval_diversity": {
                "final": round(div[-1], 4) if div else 0,
                "avg": round(sum(div) / len(div), 4) if div else 0,
            },
            "memory": {
                "final_total": self.data["memory_total"][-1] if self.data["memory_total"] else 0,
                "final_semantic": self.data["memory_semantic"][-1] if self.data["memory_semantic"] else 0,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4: PATHOLOGY DETECTOR (observe only, NO intervention)
# ─────────────────────────────────────────────────────────────────────────────

class PathologyDetector:
    """
    Detects runtime behavioral pathologies.
    
    Detects:
      1. Semantic monopolization (semantic retrieval share > threshold)
      2. Archive explosion (growth rate > threshold)
      3. Latency spike (current > 3x recent average)
      4. Retrieval stagnation (same items retrieved repeatedly)
      5. GC growth explosion
      6. Memory explosion
    
    All detection is OBSERVATION ONLY. No patches.
    """

    def __init__(self, thresholds: dict = None):
        t = thresholds or {}
        self.SEMANTIC_MONOPOLY = t.get("semantic_monopoly", SEMANTIC_MONOPOLY_THRESHOLD)
        self.ARCHIVE_EXPLOSION = t.get("archive_explosion", ARCHIVE_EXPLOSION_RATE)
        self.LATENCY_SPIKE = t.get("latency_spike", LATENCY_SPIKE_MULTIPLIER)
        self.STAGNATION = t.get("stagnation", RETRIEVAL_STAGNATION_TICKS)
        self.GC_GROWTH = t.get("gc_growth", GC_GROWTH_THRESHOLD)
        
        self.findings = []  # All pathology findings (observe only)
        self._archive_history = []
        self._retrieval_id_buffer = []
        self._gc_history = []
        self._semantic_share_history = []
    
    def detect(self, tick: int, lm: LayeredMemory,
               retrieval_result: list, latency_ms: float,
               gc_ops: int, semantic_share: float,
               explainer: RetrievalExplainer) -> list:
        """
        Run all pathology checks for this tick.
        Returns list of detected pathologies (observation only).
        """
        detected = []
        
        # 1. Semantic monopolization
        if tick > 1000 and semantic_share > self.SEMANTIC_MONOPOLY:
            finding = {
                "tick": tick, "type": "semantic_monopolization",
                "severity": "HIGH" if semantic_share > 0.75 else "MEDIUM",
                "value": round(semantic_share, 4),
                "threshold": self.SEMANTIC_MONOPOLY,
                "details": f"semantic retrieval share={semantic_share:.1%} > {self.SEMANTIC_MONOPOLY:.1%}"
            }
            detected.append(finding)
        
        # 2. Archive explosion (check every 1000 ticks)
        self._archive_history.append(len(lm.archive))
        if len(self._archive_history) >= 1000:
            old = self._archive_history[-2000] if len(self._archive_history) >= 2000 else self._archive_history[0]
            new = self._archive_history[-1]
            growth = (new - old) / max(old, 1)
            if growth > self.ARCHIVE_EXPLOSION:
                finding = {
                    "tick": tick, "type": "archive_explosion",
                    "severity": "MEDIUM",
                    "value": round(growth, 4),
                    "threshold": self.ARCHIVE_EXPLOSION,
                    "details": f"archive grew {growth:.1%} over last 1000 ticks ({old} → {new})"
                }
                detected.append(finding)
        
        # 3. Latency spike
        lat_history = explainer.history[-100:]
        if len(lat_history) >= 20:
            recent_avg = sum(e["latency_ms"] for e in lat_history[-20:]) / 20
            if latency_ms > recent_avg * self.LATENCY_SPIKE:
                finding = {
                    "tick": tick, "type": "latency_spike",
                    "severity": "HIGH" if latency_ms > recent_avg * 5 else "MEDIUM",
                    "value": round(latency_ms, 4),
                    "recent_avg_ms": round(recent_avg, 4),
                    "multiplier": round(latency_ms / max(recent_avg, 0.0001), 2),
                    "details": f"latency={latency_ms:.4f}ms, recent_avg={recent_avg:.4f}ms"
                }
                detected.append(finding)
        
        # 4. Retrieval stagnation
        ids = tuple(sorted([m.get("id") for m in retrieval_result]))
        self._retrieval_id_buffer.append(ids)
        if len(self._retrieval_id_buffer) > self.STAGNATION:
            recent = self._retrieval_id_buffer[-self.STAGNATION:]
            unique = len(set(recent))
            if unique < 3:  # Very few unique retrieval sets
                finding = {
                    "tick": tick, "type": "retrieval_stagnation",
                    "severity": "MEDIUM",
                    "unique_retrieval_sets": unique,
                    "window": self.STAGNATION,
                    "details": f"only {unique} unique retrieval sets in last {self.STAGNATION} ticks"
                }
                detected.append(finding)
        
        # 5. GC growth explosion
        self._gc_history.append(gc_ops)
        if len(self._gc_history) >= 2000:
            early = sum(self._gc_history[:1000]) / 1000
            late = sum(self._gc_history[-1000:]) / 1000
            if early > 0 and late / early > self.GC_GROWTH:
                finding = {
                    "tick": tick, "type": "gc_growth_explosion",
                    "severity": "MEDIUM",
                    "early_avg": round(early, 4),
                    "late_avg": round(late, 4),
                    "ratio": round(late / max(early, 0.0001), 4),
                    "details": f"GC grew {late/early:.2f}x over 2000 ticks ({early:.2f} → {late:.2f})"
                }
                detected.append(finding)
        
        # 6. Memory explosion (total > 10 * ticks)
        total = (len(lm.working) + len(lm.episodic) + 
                 len(lm.semantic) + len(lm.archive))
        if total > tick * 0.5:  # More than 0.5 memories per tick (very loose)
            finding = {
                "tick": tick, "type": "memory_explosion",
                "severity": "LOW",
                "value": total,
                "tick": tick,
                "details": f"total_memories={total} > {tick * 0.5:.0f} threshold"
            }
            detected.append(finding)
        
        # Log all findings (observe only)
        for f in detected:
            if not any(x["type"] == f["type"] and x["tick"] == f["tick"] 
                      for x in self.findings):
                self.findings.append(f)
        
        return detected
    
    def summary(self) -> dict:
        by_type = defaultdict(list)
        for f in self.findings:
            by_type[f["type"]].append(f)
        
        return {
            "total_findings": len(self.findings),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "top_findings": self.findings[:20],
        }


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5: TICK SNAPSHOT SAMPLER
# Periodic deep snapshots of memory state
# ─────────────────────────────────────────────────────────────────────────────

class SnapshotSampler:
    """
    Saves periodic deep snapshots of memory state.
    
    Each snapshot contains:
      - Memory counts per layer
      - Top 5 by importance per layer
      - Top 5 by access_count per layer
      - GC state
      - Latency histogram (last 100)
    """

    def __init__(self, output_dir: str, interval: int = SNAPSHOT_EVERY):
        self.output_dir = output_dir
        self.interval = interval
        self.snapshots = []
    
    def maybe_save(self, tick: int, lm: LayeredMemory, 
                   latency_history: list, gc_ops: int,
                   explainer: RetrievalExplainer):
        """Save snapshot if tick % interval == 0."""
        if tick % self.interval != 0:
            return
        
        def top_k(layer: list, key: str, k: int = 5) -> list:
            sorted_layer = sorted(layer, key=lambda m: m.get(key, 0), reverse=True)
            return [
                {
                    "id": m.get("id"),
                    "content": m.get("content", "")[:50],
                    "importance": m.get("importance"),
                    "access_count": m.get("access_count", 0),
                    "last_access_tick": m.get("last_access_tick", 0),
                    "state": m.get("state"),
                    "created_tick": m.get("created_tick", 0),
                }
                for m in sorted_layer[:k]
            ]
        
        recent_latencies = [e["latency_ms"] for e in latency_history[-100:]]
        
        snap = {
            "tick": tick,
            "timestamp": datetime.now().isoformat(),
            "memory": {
                "working_count": len(lm.working),
                "episodic_count": len(lm.episodic),
                "semantic_count": len(lm.semantic),
                "archive_count": len(lm.archive),
            },
            "top_by_importance": {
                "working": top_k(lm.working, "importance"),
                "episodic": top_k(lm.episodic, "importance"),
                "semantic": top_k(lm.semantic, "importance"),
            },
            "top_by_access": {
                "working": top_k(lm.working, "access_count"),
                "episodic": top_k(lm.episodic, "access_count"),
                "semantic": top_k(lm.semantic, "access_count"),
            },
            "gc_ops_this_tick": gc_ops,
            "latency": {
                "current_ms": recent_latencies[-1] if recent_latencies else 0,
                "avg_100": round(sum(recent_latencies) / len(recent_latencies), 4) if recent_latencies else 0,
                "max_100": round(max(recent_latencies), 4) if recent_latencies else 0,
            },
            "retrieval_layer_share": explainer.get_layer_share(),
            "rerank_stats": explainer.rerank_stats.copy(),
        }
        
        self.snapshots.append(snap)
        
        # Also save to disk
        path = os.path.join(self.output_dir, f"snap_{tick}.json")
        with open(path, "w") as f:
            json.dump(snap, f, indent=2)
        
        return snap
    
    def summary(self) -> dict:
        return {
            "total_snapshots": len(self.snapshots),
            "snap_ticks": [s["tick"] for s in self.snapshots],
        }


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC WORKLOAD GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class SyntheticWorkload:
    """Generates realistic synthetic memory workload."""

    def __init__(self, seed=RANDOM_SEED):
        random.seed(seed)
        self.tick = 0

    def memory_write(self, lm: LayeredMemory) -> list:
        """Generate 1-3 memories per tick."""
        self.tick += 1
        written = []
        for _ in range(random.randint(1, 3)):
            topic = random.choice(TOPICS)
            template = random.choice(TEMPLATES)
            content = template.format(
                topic=topic, n=random.randint(1, 999),
                s=random.choice(STATUSES), e=random.choice(ENVS),
                t=random.choice(TEAMS), c=random.choice(COMPS),
                w=random.choice(PEOPLE), q=f"Q{random.randint(1, 4)}",
            )
            importance = random.uniform(0.3, 0.95)
            mid = lm.store(content, "general", importance, [topic], self.tick)
            written.append(mid)
        
        # Adversarial noise (10%)
        if random.random() < 0.1:
            noise = f"irrelevant_noise_{random.randint(1, 10000)} at tick {self.tick}"
            lm.store(noise, "noise", 0.1, ["noise"], self.tick)
        
        return written

    def query(self) -> str:
        """Generate a retrieval query."""
        if random.random() < 0.7:
            return random.choice(TOPICS)
        else:
            return random.choice(TOPICS) + " " + random.choice(TOPICS)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RUNTIME PHYSICS OBSERVER
# ─────────────────────────────────────────────────────────────────────────────

class RuntimePhysicsObserver:
    """
    Full observability layer for MCR runtime physics.
    
    Composition of all 5 modules.
    """

    def __init__(self, ticks=TICKS):
        self.ticks = ticks
        self.start_time = time.time()
        
        # Core memory (clean state)
        self.lm = LayeredMemory(RUN_DATA_DIR)
        
        # Module 1: Transition trace
        log_path = os.path.join(RUN_DATA_DIR, "transitions.jsonl")
        self.transition_trace = TransitionTrace(log_path)
        
        # Module 2: Retrieval explainer
        self.explainer = RetrievalExplainer(self.lm)
        
        # Module 3: Metrics timeline
        self.metrics = MetricsTimeline()
        
        # Module 4: Pathology detector
        self.pathology_detector = PathologyDetector()
        
        # Module 5: Snapshot sampler
        self.snapshot_sampler = SnapshotSampler(RUN_DATA_DIR)
        
        # Workload
        self.workload = SyntheticWorkload()
        
        # Tick history for explainer
        self._retrieval_explanation_history = []

    def run(self):
        """Run the full observability loop."""
        print(f"\n{'='*60}")
        print(f"RUNTIME PHYSICS OBSERVER — {self.ticks} ticks (Path A)")
        print(f"Observability: Transition | Retrieval | Metrics | Pathology | Snapshots")
        print(f"{'='*60}")
        
        for tick in range(1, self.ticks + 1):
            # ── Step 1: Memory Write ──
            self.workload.memory_write(self.lm)
            
            # ── Step 2: Retrieval (with explainability) ──
            query = self.workload.query()
            _, latency_ms, retrieval_result = None, 0, []
            
            t0 = time.perf_counter()
            result, explanation = self.explainer.retrieve(
                query=query,
                current_goal=query,
                current_tick=tick,
                max_results=5,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            retrieval_result = result
            
            self._retrieval_explanation_history.append(explanation)
            
            # ── Step 3: Lifecycle ──
            decay_result = self.lm.process_decay_buffer(tick)
            review_result = self.lm.incremental_review(tick)
            gc_ops = (
                len(decay_result.get("revived", [])) + 
                len(decay_result.get("deleted", [])) +
                len(review_result.get("promoted_to_semantic", [])) +
                len(review_result.get("archived", []))
            )
            
            # ── Step 4: Metrics Collection ──
            rerank_rate = self.explainer.get_rerank_rate()
            self.metrics.record_tick(tick, self.lm, retrieval_result, 
                                      latency_ms, gc_ops, rerank_rate)
            self.metrics.record_semantic_share(self.explainer)
            
            # ── Step 5: Pathology Detection (observe only) ──
            semantic_share = self.explainer.get_layer_share().get("semantic", 0)
            pathologies = self.pathology_detector.detect(
                tick, self.lm, retrieval_result, latency_ms,
                gc_ops, semantic_share, self.explainer
            )
            
            # ── Step 6: Snapshot Sampling ──
            self.snapshot_sampler.maybe_save(
                tick, self.lm, self._retrieval_explanation_history,
                gc_ops, self.explainer
            )
            
            # ── Step 7: Periodic Report ──
            if tick % REPORT_EVERY == 0:
                self._report(tick)
            
            # Flush periodically
            if tick % 100 == 0:
                self.lm.try_flush(tick)
        
        self._final_report()
        self._save_data()
    
    def _report(self, tick: int):
        """Print periodic status report."""
        elapsed = time.time() - self.start_time
        m = self.metrics
        
        # Memory
        wc = self.metrics.data["memory_working"][-1]
        ec = self.metrics.data["memory_episodic"][-1]
        sc = self.metrics.data["memory_semantic"][-1]
        ac = self.metrics.data["memory_archive"][-1]
        total = wc + ec + sc + ac
        
        # Latency
        lat = self.metrics.data["latency_ms"]
        recent_lat = lat[-1000:] if len(lat) >= 1000 else lat
        avg_lat = sum(recent_lat) / len(recent_lat) if recent_lat else 0
        max_lat = max(recent_lat) if recent_lat else 0
        
        # Semantic share
        ss = self.metrics.data["semantic_share"]
        avg_ss = sum(ss[-1000:]) / len(ss[-1000:]) if ss else 0
        
        # GC
        gc = self.metrics.data["gc_ops"]
        avg_gc = sum(gc[-1000:]) / len(gc[-1000:]) if gc else 0
        
        # Pathology
        path_count = len(self.pathology_detector.findings)
        
        print(f"\n[TICK {tick}/{self.ticks}] ({elapsed:.1f}s elapsed)")
        print(f"  Memory: total={total} (W={wc} E={ec} S={sc} A={ac})")
        print(f"  Latency: avg={avg_lat:.4f}ms max={max_lat:.4f}ms")
        print(f"  Semantic share: {avg_ss:.1%}")
        print(f"  GC: {avg_gc:.2f} ops/tick")
        print(f"  Pathologies: {path_count}")
    
    def _final_report(self):
        """Print final comprehensive report."""
        elapsed = time.time() - self.start_time
        m_summary = self.metrics.summary()
        p_summary = self.pathology_detector.summary()
        
        # Reload transitions for analysis
        self.transition_trace.reload()
        t_summary = self.transition_trace.summary()
        
        print(f"\n{'='*60}")
        print(f"FINAL REPORT — Runtime Physics ({self.ticks} ticks, {elapsed:.1f}s)")
        print(f"{'='*60}")
        
        # ── Bounded Properties ──
        lat = m_summary["latency"]
        gc = m_summary["gc"]
        
        print(f"\n[BOUNDED PROPERTIES]")
        
        lat_ok = lat["ratio"] < 10
        print(f"  Latency: {lat['avg_ms']}ms avg | {lat['max_ms']}ms max")
        print(f"    Early→Late: {lat['early_avg_ms']}ms → {lat['late_avg_ms']}ms = {lat['ratio']:.2f}x {'✓' if lat_ok else '✗'}")
        
        gc_ok = gc["ratio"] < GC_GROWTH_THRESHOLD
        print(f"  GC: {gc['avg_per_tick']:.2f} ops/tick avg")
        print(f"    Early→Late: {gc['early_avg']:.2f} → {gc['late_avg']:.2f} = {gc['ratio']:.2f}x {'✓' if gc_ok else '⚠'}")
        
        print(f"  Semantic share: {m_summary['semantic_share']['avg']:.1%} avg, {m_summary['semantic_share']['max']:.1%} max")
        print(f"  Retrieval diversity: {m_summary['retrieval_diversity']['final']:.1%} (unique/total)")
        print(f"  Memory total: {m_summary['memory']['final_total']}")
        print(f"  Semantic layer: {m_summary['memory']['final_semantic']}")
        
        # ── Retrieval Explainability ──
        print(f"\n[RETRIEVAL EXPLAINABILITY]")
        ls = self.explainer.get_layer_share()
        print(f"  Layer share: W={ls['working']:.1%} E={ls['episodic']:.1%} S={ls['semantic']:.1%} A={ls['archive']:.1%}")
        rr = self.explainer.get_rerank_rate()
        print(f"  Rerank rate: {rr:.1%} of retrievals had modifications")
        rs = self.explainer.rerank_stats
        print(f"  Rerank breakdown: suppressed={rs['suppressed']} replaced={rs['replaced']} overridden={rs['overridden']}")
        
        # ── Transition Trace ──
        print(f"\n[TRANSITION TRACE]")
        print(f"  Total transitions: {t_summary['total_transitions']}")
        if t_summary['avg_lifetime']:
            print(f"  Avg memory lifetime: {t_summary['avg_lifetime']:.1f} ticks")
        print(f"  Top promotion reasons: {t_summary['top_promotion_reasons']}")
        print(f"  Top state transitions: {t_summary['transition_graph']}")
        
        # ── Pathology Catalog ──
        print(f"\n[PATHOLOGY CATALOG]")
        print(f"  Total findings: {p_summary['total_findings']}")
        for ptype, count in p_summary['by_type'].items():
            print(f"    {ptype}: {count}")
        if p_summary['top_findings']:
            print(f"  Sample findings:")
            for f in p_summary['top_findings'][:5]:
                print(f"    [{f['severity']}] {f['type']} @ tick {f['tick']}: {f['details']}")
        
        # ── Verdict ──
        print(f"\n[VERDICT]")
        verdicts = []
        if lat["ratio"] < 10:
            verdicts.append("✓ LATENCY BOUNDED")
        else:
            verdicts.append("✗ LATENCY EXPLODING")
        if gc["ratio"] < GC_GROWTH_THRESHOLD:
            verdicts.append("✓ GC BOUNDED")
        else:
            verdicts.append("⚠ GC GROWING (observe longer)")
        if p_summary["total_findings"] == 0:
            verdicts.append("✓ ZERO PATHOLOGIES")
        else:
            high = sum(1 for f in p_summary["top_findings"] if f["severity"] == "HIGH")
            if high > 0:
                verdicts.append(f"⚠ {high} HIGH-SEVERITY PATHOLOGIES")
            else:
                verdicts.append(f"✓ {p_summary['total_findings']} PATHOLOGIES (all MEDIUM/LOW)")
        for v in verdicts:
            print(f"  {v}")
    
    def _save_data(self):
        """Save all data to disk."""
        # Metrics
        metrics_path = os.path.join(RUN_DATA_DIR, "metrics_timeline.json")
        with open(metrics_path, "w") as f:
            json.dump(self.metrics.data, f, indent=2)
        
        # Pathology
        path_path = os.path.join(RUN_DATA_DIR, "pathology_findings.json")
        with open(path_path, "w") as f:
            json.dump(self.pathology_detector.findings, f, indent=2)
        
        # Snapshots summary
        snap_path = os.path.join(RUN_DATA_DIR, "snapshots_summary.json")
        with open(snap_path, "w") as f:
            json.dump(self.snapshot_sampler.summary(), f, indent=2)
        
        # Transition trace
        trace_path = os.path.join(RUN_DATA_DIR, "transition_analysis.json")
        self.transition_trace.reload()
        with open(trace_path, "w") as f:
            json.dump(self.transition_trace.summary(), f, indent=2)
        
        # Retrieval explainer history (first 200 only to save space)
        retrieval_path = os.path.join(RUN_DATA_DIR, "retrieval_explanations.json")
        with open(retrieval_path, "w") as f:
            json.dump(self._retrieval_explanation_history[:200], f, indent=2)
        
        print(f"\n[DATA SAVED]")
        for path in [metrics_path, path_path, snap_path, trace_path, retrieval_path]:
            size = os.path.getsize(path)
            print(f"  {os.path.basename(path)}: {size:,} bytes")


# ─────────────────────────────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("MCR Runtime Physics Observer — Enhanced (Path A: Observability)")
    print(f"Observation dir: {OBSERVATION_DIR}")
    print(f"Data dir: {RUN_DATA_DIR}")
    print(f"LKG: v0.19g — hash: 637a11c907e8a889b909513522dfab8c")
    
    observer = RuntimePhysicsObserver(ticks=TICKS)
    observer.run()
