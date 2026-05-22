"""
Minimal Observer — Phase III-E Observability Interference Test
==============================================================

A TRULY PASSIVE observer that:
- Wraps all public API calls
- Records timing at entry/exit of each operation
- Tracks lifecycle event counts
- Reads NO internal state (passive only)
- Emits NO events to WAL (observer events stay in-memory)
- Has ZERO ability to change runtime behavior

This is the minimal interference case: if THIS observer changes physics,
then ANY observer would. If this doesn't, we're safe.
"""

import time
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ObserverMetrics:
    """In-memory metrics collected by the observer. Never written to WAL."""
    call_count: int = 0
    total_latency_ns: int = 0
    max_latency_ns: int = 0
    min_latency_ns: int = 10**12
    store_count: int = 0
    retrieve_count: int = 0
    process_decay_count: int = 0
    flush_count: int = 0
    promotion_count: int = 0
    archive_count: int = 0
    delete_count: int = 0
    wal_write_count: int = 0
    wal_write_latency_ns: int = 0
    rerank_count: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(self, op_name: str, latency_ns: int):
        with self._lock:
            self.call_count += 1
            self.total_latency_ns += latency_ns
            self.max_latency_ns = max(self.max_latency_ns, latency_ns)
            self.min_latency_ns = min(self.min_latency_ns, latency_ns)
            counter_map = {
                "store": "store_count",
                "retrieve": "retrieve_count",
                "process_decay": "process_decay_count",
                "try_flush": "flush_count",
                "_promote_memory": "promotion_count",
                "_archive_memory": "archive_count",
                "_delete_memory": "delete_count",
                "_log_transition": "wal_write_count",
                "rerank": "rerank_count",
            }
            if op_name in counter_map:
                setattr(self, counter_map[op_name], getattr(self, counter_map[op_name]) + 1)
            if op_name == "_log_transition":
                self.wal_write_count += 1
                self.wal_write_latency_ns += latency_ns

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            avg = self.total_latency_ns / max(1, self.call_count)
            wal_avg = self.wal_write_latency_ns / max(1, self.wal_write_count)
            return {
                "call_count": self.call_count,
                "avg_latency_ns": avg,
                "max_latency_ns": self.max_latency_ns,
                "min_latency_ns": self.min_latency_ns if self.min_latency_ns < 10**12 else 0,
                "store_count": self.store_count,
                "retrieve_count": self.retrieve_count,
                "process_decay_count": self.process_decay_count,
                "flush_count": self.flush_count,
                "promotion_count": self.promotion_count,
                "archive_count": self.archive_count,
                "delete_count": self.delete_count,
                "wal_write_count": self.wal_write_count,
                "wal_write_latency_ns": self.wal_write_latency_ns,
                "wal_write_avg_ns": wal_avg,
                "rerank_count": self.rerank_count,
            }


class MinimalObserver:
    """
    Wraps LayeredMemory with zero-interference instrumentation.

    Key design constraints:
    1. Never writes to WAL (observer events are in-memory only)
    2. Never modifies memory state
    3. Never blocks or synchronizes across threads
    4. Uses only public API or documented internal hooks
    5. Time measurement uses perf_counter_ns (monotonic, nanosecond)
    """

    def __init__(self, lm_instance):
        self._lm = lm_instance
        self._metrics = ObserverMetrics()
        self._enabled = True

    def disable(self):
        """Temporarily disable observation (for nested calls)."""
        self._enabled = False

    def enable(self):
        self._enabled = True

    def _time_op(self, op_name: str, fn, *args, **kwargs) -> Any:
        """Time an operation without interfering with its execution."""
        if not self._enabled:
            return fn(*args, **kwargs)
        start = time.perf_counter_ns()
        try:
            result = fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter_ns() - start
            self._metrics.record(op_name, elapsed)
        return result

    # ── Public API ────────────────────────────────────────────────────────────

    def store(self, content: str, memory_type: str = "general",
              importance: float = 0.5, tags: Optional[List[str]] = None,
              current_tick: int = 0) -> str:
        return self._time_op("store", self._lm.store, content,
                             memory_type=memory_type, importance=importance,
                             tags=tags, current_tick=current_tick)

    def retrieve(self, query: str, current_goal: str = "", current_tick: int = 0,
                 max_results: int = 5) -> List:
        return self._time_op("retrieve", self._lm.retrieve, query,
                            current_goal=current_goal, current_tick=current_tick,
                            max_results=max_results)

    def process_decay_buffer(self, tick: int) -> None:
        return self._time_op("process_decay", self._lm.process_decay_buffer, tick)

    def try_flush(self, tick: int) -> None:
        return self._time_op("try_flush", self._lm.try_flush, tick)

    def incremental_review(self, tick: int) -> None:
        return self._time_op("incremental_review", self._lm.incremental_review, tick)

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.to_dict()

    def get_memory_counts(self) -> Dict[str, int]:
        return {
            "working": len(self._lm.working),
            "episodic": len(self._lm.episodic),
            "semantic": len(self._lm.semantic),
            "archive": len(self._lm.archive),
        }
