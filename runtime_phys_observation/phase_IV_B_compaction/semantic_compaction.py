"""
Semantic Compaction Layer — Phase IV-B
======================================

Deterministic semantic merge physics for MCR.

GOAL: Multiple similar episodic memories → merge into stable semantic_summary node.
      NOT LLM summarization. NOT embedding clustering.
      Deterministic co-access pattern merge.

CORE CONCEPT:
  Current semantic = rerank layer (filtered out by prefilter)
  Target semantic = compressed cognition (semantic_summary nodes)

MECHANISM:
  episodic redundancy detection
    → content_hash collision (simulated via shared prefix + shared tags)
    → co-access pattern (memories accessed together within Δtick)
    → compaction trigger
    → semantic_summary node generation
    → original memories → cold/archive
    → summary → semantic tier anchor
    → retrieval优先summary, detail按需从archived展开

NO AGENT. NO LLM. NO recursive reflection.
Only deterministic merge physics.
"""

import json
import hashlib
import sys
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

# Import MCR core modules
sys.path.insert(0, str(Path(__file__).parent.parent / "stable"))
from layered_memory import LayeredMemory
from wal_manager import WALManager


# ── Semantic Summary Node ──────────────────────────────────────────────────────

@dataclass
class SemanticSummary:
    """
    Deterministic semantic_summary node.

    NOT a text summary (no LLM). A compressed representation built from:
    - content centroid (shared prefix from source memories)
    - shared tags (intersection of source tags)
    - centroid vector (average of source importance/access patterns)
    - source_memory_ids (ordered list of merged memory IDs)
    """
    summary_id: str
    summary_content: str          # Shared prefix of source contents
    summary_tags: List[str]      # Intersection of source tags
    centroid_importance: float
    centroid_access_weight: float
    centroid_access_count: float
    source_memory_ids: List[str]
    source_count: int
    compression_ratio: float
    retrieval_hit_rate: float = 0.0
    entropy_delta: float = 0.0
    tick_created: int = 0
    last_access_tick: int = 0
    state: str = "semantic"

    def to_dict(self) -> Dict:
        return {
            "id": self.summary_id,
            # Shared prefix — deterministic LCP of source contents (hash-stable)
            "content": self.summary_content,
            "tags": self.summary_tags,
            # TASK 2: explicit summary structure
            "topic": self.summary_tags[0] if self.summary_tags else "unknown",
            "members": self.source_memory_ids,
            "centroid_vector": {
                "importance": self.centroid_importance,
                "access_weight": self.centroid_access_weight,
                "access_count": self.centroid_access_count,
            },
            "representative_terms": self.summary_tags[:5],
            # Legacy fields
            "importance": self.centroid_importance,
            "access_weight": self.centroid_access_weight,
            "access_count": self.centroid_access_count,
            "source_memory_ids": self.source_memory_ids,
            "source_count": self.source_count,
            "compression_ratio": self.compression_ratio,
            "retrieval_hit_rate": self.retrieval_hit_rate,
            "entropy_delta": self.entropy_delta,
            "tick_created": self.tick_created,
            "last_access_tick": self.last_access_tick,
            "state": self.state,
            "memory_type": "semantic_summary",
        }

    @staticmethod
    def from_dict(d: Dict) -> 'SemanticSummary':
        cv = d.get("centroid_vector", {})
        return SemanticSummary(
            summary_id=d["id"],
            summary_content=d.get("content", ""),
            summary_tags=d.get("tags", []),
            centroid_importance=cv.get("importance", d.get("importance", 0.5)),
            centroid_access_weight=cv.get("access_weight", d.get("access_weight", 1.0)),
            centroid_access_count=cv.get("access_count", d.get("access_count", 1.0)),
            source_memory_ids=d.get("source_memory_ids", d.get("members", [])),
            source_count=d.get("source_count", len(d.get("source_memory_ids", d.get("members", [])))),
            compression_ratio=d.get("compression_ratio", 1.0),
            retrieval_hit_rate=d.get("retrieval_hit_rate", 0.0),
            entropy_delta=d.get("entropy_delta", 0.0),
            tick_created=d.get("tick_created", 0),
            last_access_tick=d.get("last_access_tick", 0),
            state=d.get("state", "semantic"),
        )

    @staticmethod
    def from_memories(memories: List[Dict], tick: int,
                      entropy_delta: float = 0.0) -> 'SemanticSummary':
        """
        Deterministic merge of N memories into 1 semantic_summary.

        Rules:
        - summary_content = shared longest common prefix
        - summary_tags = intersection of all source tags
        - centroid_importance = mean of source importances
        - centroid_access_weight = mean of source access_weights
        - centroid_access_count = mean of source access_counts
        - summary_id = hash of (sorted source IDs) — deterministic
        """
        if not memories:
            raise ValueError("Cannot merge zero memories")

        # Deterministic ID from sorted source IDs
        sorted_ids = sorted(m["id"] for m in memories)
        id_input = "|".join(sorted_ids)
        summary_id = "sem_" + hashlib.md5(id_input.encode()).hexdigest()[:12]

        # Content: longest common prefix
        contents = [m.get("content", "") for m in memories]
        shared_prefix = _longest_common_prefix(contents)

        # Tags: intersection
        all_tags: Set[str] = set()
        for m in memories:
            all_tags.update(m.get("tags", []))
        shared_tags = sorted(all_tags)

        # Centroid statistics
        centroid_importance = sum(m.get("importance", 0.5) for m in memories) / len(memories)
        centroid_access_weight = sum(m.get("access_weight", 1.0) for m in memories) / len(memories)
        centroid_access_count = sum(m.get("access_count", 1) for m in memories) / len(memories)

        return SemanticSummary(
            summary_id=summary_id,
            summary_content=shared_prefix,
            summary_tags=shared_tags,
            centroid_importance=centroid_importance,
            centroid_access_weight=centroid_access_weight,
            centroid_access_count=centroid_access_count,
            source_memory_ids=sorted_ids,
            source_count=len(memories),
            compression_ratio=float(len(memories)),
            retrieval_hit_rate=0.0,
            entropy_delta=entropy_delta,
            tick_created=tick,
            last_access_tick=tick,
            state="semantic",
        )


def _longest_common_prefix(strs: List[str]) -> str:
    """Deterministic longest common prefix."""
    if not strs:
        return ""
    if len(strs) == 1:
        return strs[0]
    prefix = strs[0]
    for s in strs[1:]:
        if not prefix:
            break
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                break
    return prefix


# ── Co-Access Graph ────────────────────────────────────────────────────────────

@dataclass
class CoAccessGraph:
    """
    Tracks which memories are accessed together.
    Used for episodic redundancy detection.

    Two memories are "co-accessed" if they appear in the same
    retrieval session within COACCESS_WINDOW ticks.

    PHASE_VI PATCH — Death Mechanisms:
    * EDGE_DECAY: edge weights multiplied by DECAY_FACTOR each tick
    * PER_NODE_CAP: max MAX_EDGES_PER_NODE neighbors per memory_id
    * GLOBAL_CAP: max MAX_TOTAL_EDGES total across all nodes

    PHASE_VII (Tombstone) — Memory Lifecycle Sync:
    * TOMBSTONE: tombstoned memories are excluded from coaccess lookups
    * PURGE: purged memories have all their edges removed
    """
    edges: Dict[str, Dict[str, float]] = field(default_factory=dict)
    access_order: List[Tuple[int, str]] = field(default_factory=list)
    COACCESS_WINDOW: int = 50
    # PHASE_VI death mechanism params
    DECAY_FACTOR: float = 0.995       # per-tick decay — old edges fade
    MAX_EDGES_PER_NODE: int = 20      # per-node neighbor cap
    MAX_TOTAL_EDGES: int = 500        # global edge cap
    MIN_EDGE_WEIGHT: float = 0.5      # below this → delete edge
    # PHASE_VII tombstoned set
    tombstoned_mids: Set[str] = field(default_factory=set)

    def is_active(self, memory_id: str) -> bool:
        """True if memory_id is not tombstoned or purged."""
        return memory_id not in self.tombstoned_mids

    def remove_memory(self, memory_id: str) -> int:
        """
        Remove all edges for a memory_id (called on purge).
        Returns number of edges removed.
        """
        removed = 0
        if memory_id in self.edges:
            n_edges = len(self.edges[memory_id])
            del self.edges[memory_id]
            removed += n_edges
        for other, neighs in self.edges.items():
            if memory_id in neighs:
                del neighs[memory_id]
                removed += 1
        if memory_id in self.tombstoned_mids:
            self.tombstoned_mids.discard(memory_id)
        return removed

    def decay_edges(self) -> int:
        """
        Apply decay to all edge weights.
        Remove edges below MIN_EDGE_WEIGHT.
        Returns number of edges removed.
        """
        to_delete = []
        for mem_a, neighs in self.edges.items():
            for mem_b in list(neighs.keys()):
                neighs[mem_b] *= self.DECAY_FACTOR
                if neighs[mem_b] < self.MIN_EDGE_WEIGHT:
                    to_delete.append((mem_a, mem_b))

        for mem_a, mem_b in to_delete:
            if mem_a in self.edges and mem_b in self.edges[mem_a]:
                del self.edges[mem_a][mem_b]
            if mem_b in self.edges and mem_a in self.edges[mem_b]:
                del self.edges[mem_b][mem_a]
        return len(to_delete)

    def cap_edges(self) -> int:
        """
        Enforce MAX_EDGES_PER_NODE and MAX_TOTAL_EDGES.
        Removes lowest-weight edges first.
        Returns number of edges removed.
        """
        removed = 0

        # Per-node cap
        for mem_id, neighs in list(self.edges.items()):
            if len(neighs) <= self.MAX_EDGES_PER_NODE:
                continue
            sorted_neighs = sorted(neighs.items(), key=lambda x: x[1])
            to_keep = dict(sorted_neighs[-self.MAX_EDGES_PER_NODE:])
            to_remove = set(neighs.keys()) - set(to_keep.keys())
            for nb in to_remove:
                del neighs[nb]
                if nb in self.edges and mem_id in self.edges[nb]:
                    del self.edges[nb][mem_id]
                removed += 1

        # Global cap
        total_edges = sum(len(n) for n in self.edges.values())
        if total_edges <= self.MAX_TOTAL_EDGES:
            return removed
        excess = total_edges - self.MAX_TOTAL_EDGES
        # Collect all edges with weights
        all_edges = []
        for mem_a, neighs in self.edges.items():
            for mem_b, w in neighs.items():
                if mem_a < mem_b:  # avoid double-count
                    all_edges.append((w, mem_a, mem_b))
        all_edges.sort(key=lambda x: x[0])  # smallest first
        to_remove_edges = all_edges[:excess]
        for _, mem_a, mem_b in to_remove_edges:
            if mem_a in self.edges and mem_b in self.edges[mem_a]:
                del self.edges[mem_a][mem_b]
            if mem_b in self.edges and mem_a in self.edges[mem_b]:
                del self.edges[mem_b][mem_a]
            removed += 1
        return removed

    def get_edge_count(self) -> int:
        """Total edge count (each edge counted once)."""
        return sum(len(n) for n in self.edges.values()) // 2

    def record_access(self, memory_id: str, tick: int) -> None:
        """Record a memory access at tick. Skips tombstoned/purged memories."""
        if not self.is_active(memory_id):
            return
        self.access_order.append((tick, memory_id))
        for prev_tick, prev_id in self.access_order[-self.COACCESS_WINDOW:]:
            if prev_id != memory_id and self.is_active(prev_id):
                if memory_id not in self.edges:
                    self.edges[memory_id] = {}
                if prev_id not in self.edges:
                    self.edges[prev_id] = {}
                # Increment by 1.0 (coaccess count, decays over time)
                self.edges[memory_id][prev_id] = self.edges[memory_id].get(prev_id, 0.0) + 1.0
                self.edges[prev_id][memory_id] = self.edges[prev_id].get(memory_id, 0.0) + 1.0
        cutoff = tick - self.COACCESS_WINDOW * 2
        self.access_order = [(t, mid) for t, mid in self.access_order if t > cutoff]

    def get_coaccess_group(self, memory_id: str, min_count: int = 2) -> List[str]:
        if memory_id not in self.edges or not self.is_active(memory_id):
            return []
        return [mid for mid, count in self.edges[memory_id].items()
                if count >= min_count and self.is_active(mid)]

    def get_redundant_groups(self, min_group_size: int = 3,
                             min_coaccess: float = 2.0) -> List[Set[str]]:
        """
        Find groups of memories that co-access each other.

        Uses connected components at min_coaccess threshold.
        NOT clique-based — tolerates sparse coaccess graphs.
        Ignores tombstoned memories.
        """
        # Build adjacency for memories with >= min_coaccess co-access edges
        neighbors: Dict[str, Set[str]] = {}
        for mem_id, neighs in self.edges.items():
            if not self.is_active(mem_id):
                continue
            strong = {n for n, c in neighs.items()
                      if c >= min_coaccess and self.is_active(n)}
            if strong:
                neighbors[mem_id] = strong

        # Connected components via BFS
        groups: List[Set[str]] = []
        visited: Set[str] = set()
        for mem_id in neighbors:
            if mem_id in visited:
                continue
            component: Set[str] = set()
            queue = [mem_id]
            while queue:
                node = queue.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                for n in neighbors.get(node, []):
                    if n not in visited:
                        queue.append(n)
            if len(component) >= min_group_size:
                groups.append(component)
        return groups


# ── Compaction Metrics ─────────────────────────────────────────────────────────

@dataclass
class CompactionMetrics:
    """Metrics for a compaction run."""
    compaction_count: int = 0
    total_memories_compacted: int = 0
    total_summaries_created: int = 0
    avg_compression_ratio: float = 0.0
    max_compression_ratio: float = 0.0
    avg_entropy_delta: float = 0.0
    retrieval_hit_rate: float = 0.0
    monopoly_events: int = 0
    information_loss_events: int = 0
    retrieval_degradation_events: int = 0
    # TASK 1 new metrics
    cross_topic_merge_count: int = 0
    same_topic_merge_count: int = 0
    cross_topic_merge_rate: float = 0.0
    semantic_purity: float = 0.0
    empty_summary_count: int = 0
    empty_summary_rate: float = 0.0
    topology_fragmentation: float = 0.0
    topic_summary_counts: Dict[str, int] = field(default_factory=dict)


# ── Semantic Compaction Engine ─────────────────────────────────────────────────

class SemanticCompaction:
    """
    Deterministic semantic compaction engine.

    Lives outside LayeredMemory. Reads episodic memories,
    builds co-access graph, detects redundancy, generates
    semantic_summary nodes, archives originals.

    WAL-compatible: logs all state transitions via WALManager.
    """

    # Compaction thresholds
    MIN_COACCESS_COUNT: int = 2          # Min co-accesses to trigger merge
    MIN_REDUNDANT_GROUP_SIZE: int = 3   # Min memories in a redundant group
    COMPACTION_INTERVAL: int = 200      # Ticks between compaction checks
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.6
    MAX_SOURCES_PER_SUMMARY: int = 10
    # TASK 1: cross-topic merge control
    MIN_TOPIC_OVERLAP: int = 1          # non-generic shared tags required
    GENERIC_TAGS: Set[str] = {
        "general", "topic_benchmark", "noise", "compaction_test",
        "unknown", "untagged",
    }
    # PHASE_VII: Tombstone Lifecycle
    PURGE_DELAY: int = 100               # ticks between tombstone and purge
    # NOTE: TOMBSTONE_INTERVAL removed — tombstoning runs every tick in v1
    # to ensure deterministic WAL replay (no async timing window)

    def __init__(self, lm, wal_manager=None):
        self._lm = lm
        self._wal = wal_manager
        self._coaccess = CoAccessGraph()
        self._tick: int = 0
        self._last_compaction_topic: str | None = None
        self._metrics = CompactionMetrics()
        self._compaction_history: List[Dict] = []
        # PHASE_VII: Tombstone state — tracks tombstoned memory metadata
        # Key: memory_id, Value: {"tombstoned_at": tick, "reason": str}
        self._tombstones: Dict[str, Dict] = {}
        self._purged_mids: Set[str] = set()    # permanently deleted mids
        # Tombstone/purge counters
        self._tombstone_count: int = 0
        self._purge_count: int = 0

    def record_access(self, memory_id: str, tick: int) -> None:
        """Record a memory access for co-access tracking."""
        self._coaccess.record_access(memory_id, tick)

    def tick(self, current_tick: int) -> None:
        """Advance compaction engine tick. Runs death mechanisms every tick."""
        self._tick = current_tick
        # PHASE_VI: Death mechanisms — run every tick
        self._coaccess.decay_edges()
        self._coaccess.cap_edges()
        # PHASE_VII: Tombstone — run every tick (no interval, deterministic)
        self.run_tombstone_check()
        # PHASE_VII: Purge — run after tombstone
        self.run_purge_check()

    def is_tombstoned(self, memory_id: str) -> bool:
        """True if memory_id is in tombstoned OR purged state."""
        return memory_id in self._tombstones or memory_id in self._purged_mids

    def run_tombstone_check(self) -> Dict:
        """
        Tombstone candidates from archive tier.
        v1 strategy: deterministic — archive items with low access weight
        are tombstoned (soft-deleted, invisible to retrieval, tracked in WAL).
        """
        if not hasattr(self._lm, "archive"):
            return {"tombstoned": 0}

        candidates = []
        for m in self._lm.archive:
            mid = m.get("id", "")
            if not mid or self.is_tombstoned(mid):
                continue
            # v1: tombstone archive items with very low access weight
            # weight = Σ decayed access, using last_access_tick as proxy
            last_access = m.get("last_access_tick", 0)
            age = self._tick - last_access
            access_weight = max(0.0, 1.0 - age * 0.02)  # fast decay
            if access_weight < 0.1 or age > 500:
                candidates.append(mid)

        tombstoned = []
        for mid in candidates:
            m = self._find_memory_by_id(self._lm.archive, mid)
            if m:
                self._lm.archive.remove(m)
                # Remove from ALL layers — an item can be in multiple layers
                # simultaneously (e.g., episodic and archive) due to compaction
                # migration. Tombstoning must clean all locations.
                for layer_name in ("working", "episodic", "semantic", "archive"):
                    layer = getattr(self._lm, layer_name, [])
                    layer[:] = [x for x in layer if x.get("id") != mid]
                self._tombstones[mid] = {
                    "tombstoned_at": self._tick,
                    "reason": "decay_below_threshold",
                    "source_tier": "archive",
                }
                self._coaccess.tombstoned_mids.add(mid)
                # WAL: archive_tombstone event
                if self._wal:
                    self._wal.append(
                        tick=self._tick,
                        type="archive_tombstone",
                        memory_id=mid,
                        from_state="archive",
                        to_state="tombstoned",
                        reason="decay_below_threshold",
                    )
                tombstoned.append(mid)
                self._tombstone_count += 1

        return {"tombstoned": len(tombstoned), "ids": tombstoned}

    def run_purge_check(self) -> Dict:
        """
        Purge candidates that have been tombstoned for >= PURGE_DELAY.
        Purged items are removed from _tombstones, coaccess edges cleaned.
        WAL archive_purge event is the only record (metadata only).
        """
        to_purge = []
        for mid, meta in list(self._tombstones.items()):
            tombstoned_at = meta.get("tombstoned_at")
            if tombstoned_at is None:
                continue  # safety
            age = self._tick - tombstoned_at
            if age >= self.PURGE_DELAY:
                to_purge.append(mid)

        purged = []
        for mid in to_purge:
            if mid not in self._tombstones:
                print(f"    [PURGE WARN] mid={mid} not in _tombstones — skipping")
                continue
            del self._tombstones[mid]
            self._coaccess.remove_memory(mid)
            self._purged_mids.add(mid)   # permanent record — blocks retrieve
            # Also physically remove from memory layers so retrieve() won't find it.
            # Use list comprehension rebuild (safe) instead of list.remove() (indirect lookup).
            # list.remove(mid) searches by VALUE (mid is a str, layer is list[dict]),
            # which silently fails when mid is not found in layer — leaving ghost items.
            self._lm.working = [m for m in self._lm.working if m.get("id") != mid]
            self._lm.episodic = [m for m in self._lm.episodic if m.get("id") != mid]
            self._lm.archive = [m for m in self._lm.archive if m.get("id") != mid]
            self._lm.semantic = [m for m in self._lm.semantic if m.get("id") != mid]
            self._purge_count += 1
            # WAL: archive_purge event
            if self._wal:
                self._wal.append(
                    tick=self._tick,
                    type="archive_purge",
                    memory_id=mid,
                    from_state="tombstoned",
                    to_state="purged",
                    reason="purge_delay_expired",
                )
            purged.append(mid)

        return {"purged": len(purged), "ids": purged}

    def _find_memory_by_id(self, layer: list, memory_id: str) -> Optional[Dict]:
        """Find memory in layer by id."""
        for m in layer:
            if m.get("id") == memory_id:
                return m
        return None

    def apply_wal_replay(self, events: list) -> Dict:
        """
        Replay WAL events to reconstruct tombstone/purge state.
        Called when a CompactionRuntime is re-opened from an existing root.

        Replaying in tick order ensures deterministic state reconstruction:
        archive_tombstone → adds to _tombstones, removes from all layers
        archive_purge     → removes from _tombstones, cleans coaccess

        NOTE: Layer transitions (episodic→semantic, etc.) are already reflected
        in the persisted storage state — storage is the ground truth for memory
        locations. We do NOT replay 'transition' events as that would cause
        double-transition (storage already contains the post-transition state).
        We only replay tombstone/purge to reconstruct the deletion path.
        """
        tombstones_applied = 0
        purges_applied = 0
        last_tick = 0
        tombstone_types_seen = set()
        purge_types_seen = set()

        # Sort events by tick for deterministic replay
        sorted_events = sorted(events, key=lambda e: (e.tick, e.seq))

        for event in sorted_events:
            last_tick = event.tick
            if event.type == "archive_tombstone":
                tombstone_types_seen.add(event.type)
                mid = event.memory_id
                if mid not in self._tombstones:
                    # Remove from ALL memory layers — this mirrors run_tombstone_check().
                    # Initial run removes item from archive when tombstoning.
                    # WAL replay must do the same, otherwise item stays in layers → ghost.
                    # Use list comprehension rebuild (avoids list.remove indirect-lookup failure).
                    self._lm.working  = [m for m in self._lm.working  if m.get("id") != mid]
                    self._lm.episodic = [m for m in self._lm.episodic if m.get("id") != mid]
                    self._lm.archive  = [m for m in self._lm.archive  if m.get("id") != mid]
                    self._lm.semantic = [m for m in self._lm.semantic if m.get("id") != mid]
                    self._tombstones[mid] = {
                        "tombstoned_at": event.tick,
                        "reason": event.reason,
                        "source_tier": "archive",
                    }
                    self._coaccess.tombstoned_mids.add(mid)
                    self._tombstone_count += 1
                    tombstones_applied += 1
            elif event.type == "archive_purge":
                purge_types_seen.add(event.type)
                mid = event.memory_id
                # Permanently remove from ALL memory layers FIRST (before state cleanup).
                # Use list comprehension rebuild — same logic as run_purge_check(),
                # but for WAL replay path. Avoids list.remove() indirect-lookup failure.
                self._lm.working  = [m for m in self._lm.working  if m.get("id") != mid]
                self._lm.episodic = [m for m in self._lm.episodic if m.get("id") != mid]
                self._lm.archive  = [m for m in self._lm.archive  if m.get("id") != mid]
                self._lm.semantic = [m for m in self._lm.semantic if m.get("id") != mid]
                # Clean up tombstone tracking
                if mid in self._tombstones:
                    del self._tombstones[mid]
                self._coaccess.remove_memory(mid)
                self._purged_mids.add(mid)   # permanent — must track for is_tombstoned()
                self._purge_count += 1
                purges_applied += 1

        self._tick = last_tick
        return {
            "tombstones_applied": tombstones_applied,
            "purges_applied": purges_applied,
            "last_tick": last_tick,
            "tombstone_types": list(tombstone_types_seen),
            "purge_types": list(purge_types_seen),
        }

    def should_compact(self) -> bool:
        """Return True if compaction should run this tick."""
        return (self._tick > 0 and
                self._tick % self.COMPACTION_INTERVAL == 0 and
                len(self._lm.episodic) >= self.MIN_REDUNDANT_GROUP_SIZE)

    def _topic_overlap(self, mem_a: Dict, mem_b: Dict) -> int:
        """
        topic_overlap = len(set(tags_a) & set(tags_b)) - generic_tags.

        Generic tags (topic_benchmark, general, noise, etc.) are excluded
        from overlap computation to prevent cross-topic contamination.
        """
        tags_a = set(mem_a.get("tags", [])) - self.GENERIC_TAGS
        tags_b = set(mem_b.get("tags", [])) - self.GENERIC_TAGS
        return len(tags_a & tags_b)

    def _coaccess_score(self, mem_a: Dict, mem_b: Dict) -> float:
        """Return co-access weight between two memories from co-access graph."""
        edges = self._coaccess.edges
        id_a = mem_a.get("id", "")
        id_b = mem_b.get("id", "")
        return float(edges.get(id_a, {}).get(id_b, 0.0))

    def run_compaction(self) -> Dict:
        """
        Run one compaction cycle — INCREMENTAL, per-topic.

        PHASE_VI CHANGE: No longer scans the full coaccess graph.
        Instead: picks ONE topic per call, processes only that topic's
        memories, bounded by MAX_MEMORIES_PER_TOPIC_SCAN.

        This changes complexity from O(n²) full-graph to O(k²) per-topic
        where k << n. The global coaccess graph still exists but we no
        longer scan it completely per compaction cycle.
        """
        if not self.should_compact():
            return {"compaction_count": 0, "summaries_created": 0}

        episodic_before = len(self._lm.episodic)
        semantic_before = len(self._lm.semantic)

        # PHASE_VI: Per-topic incremental compaction
        # Collect unique non-generic topics from episodic
        episodic_topics: Dict[str, List[Dict]] = defaultdict(list)
        for m in self._lm.episodic:
            tags = set(m.get("tags", [])) - self.GENERIC_TAGS
            if tags:
                topic = sorted(tags)[0]  # deterministic first tag
            else:
                topic = "unknown"
            episodic_topics[topic].append(m)

        if not episodic_topics:
            return {"compaction_count": 0, "summaries_created": 0}

        # Process only ONE topic per call (incremental)
        topic = self._last_compaction_topic or sorted(episodic_topics.keys())[0]
        processed_topics = sorted(episodic_topics.keys())
        current_idx = processed_topics.index(topic) if topic in processed_topics else 0
        next_idx = (current_idx + 1) % len(processed_topics)
        self._last_compaction_topic = processed_topics[next_idx]

        memories = episodic_topics[topic]
        MAX_PER_TOPIC = 30  # hard cap per topic scan
        if len(memories) > MAX_PER_TOPIC:
            memories = memories[:MAX_PER_TOPIC]

        summaries_created = []
        archived_ids = []
        compaction_events = []
        cross_topic_merges = 0
        same_topic_merges = 0
        empty_summaries = 0
        new_topic_counts: Dict[str, int] = defaultdict(int)

        # Coaccess scan within this topic's memories only
        groups = self._get_topic_groups(memories)

        for group in groups:
            if len(group) < self.MIN_REDUNDANT_GROUP_SIZE:
                continue

            # All pairs must pass coaccess + topic_overlap
            valid_group = True
            group_list = list(group)
            for i in range(len(group_list)):
                for j in range(i + 1, len(group_list)):
                    coaccess = self._coaccess_score(group_list[i], group_list[j])
                    overlap = self._topic_overlap(group_list[i], group_list[j])
                    if overlap < self.MIN_TOPIC_OVERLAP or coaccess < self.MIN_COACCESS_COUNT:
                        valid_group = False
                        break
                if not valid_group:
                    break

            if not valid_group:
                continue

            # Use group_list for deterministic iteration
            tag_freq: Dict[str, int] = defaultdict(int)
            all_tags: Set[str] = set()
            for m in group_list:
                all_tags.update(m.get("tags", []))
                for t in m.get("tags", []):
                    if t not in self.GENERIC_TAGS:
                        tag_freq[t] += 1

            dominant_tag = max(tag_freq, key=tag_freq.get) if tag_freq else topic
            distinct_topics = sum(1 for t, c in tag_freq.items() if c > 0)
            if distinct_topics > 1:
                cross_topic_merges += 1
            else:
                same_topic_merges += 1

            entropy_delta = self._compute_entropy_delta(group_list)
            summary = SemanticSummary.from_memories(group_list, self._tick, entropy_delta)

            if not summary.summary_content:
                empty_summaries += 1
                summary.summary_content = dominant_tag
                summary.summary_tags = sorted(all_tags)

            for m in group_list:
                m["state"] = "archive"
                m["last_state_change_tick"] = self._tick
                m["summary_id"] = summary.summary_id
                self._lm.archive.append(m)
                archived_ids.append(m["id"])
                self._lm.episodic.remove(m)

            summary_dict = summary.to_dict()
            self._lm.semantic.append(summary_dict)
            summaries_created.append(summary_dict)
            new_topic_counts[dominant_tag] += 1

            compaction_events.append({
                "tick": self._tick,
                "summary_id": summary.summary_id,
                "source_ids": summary.source_memory_ids,
                "source_count": summary.source_count,
                "compression_ratio": summary.compression_ratio,
                "entropy_delta": entropy_delta,
                "dominant_topic": dominant_tag,
                "is_cross_topic": distinct_topics > 1,
            })

        # Update metrics
        total_merges = cross_topic_merges + same_topic_merges
        self._metrics.compaction_count += len(summaries_created)
        self._metrics.total_memories_compacted += len(archived_ids)
        self._metrics.total_summaries_created += len(summaries_created)
        self._metrics.cross_topic_merge_count += cross_topic_merges
        self._metrics.same_topic_merge_count += same_topic_merges
        self._metrics.empty_summary_count += empty_summaries

        if total_merges > 0:
            self._metrics.cross_topic_merge_rate = cross_topic_merges / total_merges
        if len(summaries_created) > 0:
            self._metrics.semantic_purity = same_topic_merges / len(summaries_created)
            self._metrics.empty_summary_rate = empty_summaries / len(summaries_created)
            ratios = [e["compression_ratio"] for e in compaction_events]
            deltas = [e["entropy_delta"] for e in compaction_events]
            self._metrics.avg_compression_ratio = sum(ratios) / len(ratios)
            self._metrics.max_compression_ratio = max(ratios)
            self._metrics.avg_entropy_delta = sum(deltas) / len(deltas)

        if new_topic_counts:
            self._metrics.topology_fragmentation = len(new_topic_counts)
        for t, c in new_topic_counts.items():
            self._metrics.topic_summary_counts[t] = \
                self._metrics.topic_summary_counts.get(t, 0) + c

        self._compaction_history.extend(compaction_events)

        episodic_after = len(self._lm.episodic)
        semantic_after = len(self._lm.semantic)

        return {
            "compaction_count": len(summaries_created),
            "summaries_created": len(summaries_created),
            "memories_archived": len(archived_ids),
            "episodic_delta": episodic_before - episodic_after,
            "semantic_delta": semantic_after - semantic_before,
            "compaction_events": compaction_events,
            "cross_topic_merge_count": cross_topic_merges,
            "same_topic_merge_count": same_topic_merges,
            "cross_topic_merge_rate": self._metrics.cross_topic_merge_rate,
            "semantic_purity": self._metrics.semantic_purity,
            "empty_summary_count": empty_summaries,
            "topology_fragmentation": self._metrics.topology_fragmentation,
        }

    def _get_topic_groups(self, memories: List[Dict]) -> List[List[Dict]]:
        """
        PHASE_VI: Per-topic connected components — bounded by topic size.
        Returns list of memory dict groups (not ID sets).
        Only scans the subgraph induced by these memories, not the full graph.
        """
        if len(memories) < self.MIN_REDUNDANT_GROUP_SIZE:
            return []

        # Build local subgraph for these memories only
        mem_ids = {m["id"] for m in memories}
        neighbors: Dict[str, Set[str]] = {}
        for m in memories:
            mid = m["id"]
            strong = set()
            for n, w in self._coaccess.edges.get(mid, {}).items():
                if n in mem_ids and w >= self.MIN_COACCESS_COUNT:
                    strong.add(n)
            if strong:
                neighbors[mid] = strong

        # Connected components
        groups: List[List[Dict]] = []
        visited: Set[str] = set()
        for mem_id in neighbors:
            if mem_id in visited:
                continue
            component_ids: Set[str] = set()
            queue = [mem_id]
            while queue:
                node = queue.pop()
                if node in visited:
                    continue
                visited.add(node)
                component_ids.add(node)
                for n in neighbors.get(node, []):
                    if n not in visited:
                        queue.append(n)
            if len(component_ids) >= self.MIN_REDUNDANT_GROUP_SIZE:
                # Convert IDs back to memory dicts
                id_to_mem = {m["id"]: m for m in memories}
                groups.append([id_to_mem[mid] for mid in component_ids if mid in id_to_mem])
        return groups

    def _compute_entropy_delta(self, memories: List[Dict]) -> float:
        """
        Compute semantic tier entropy change from merging these memories.

        H_before = entropy of individual access weights
        H_after  = entropy of merged centroid weight (1 item → H=0)

        delta = H_after - H_before
        Negative delta = compression (information reduction from merge).
        """
        if len(memories) <= 1:
            return 0.0
        weights = [float(m.get("access_weight", 1.0)) for m in memories]
        total = sum(weights)
        if total == 0:
            return 0.0
        probs = [w / total for w in weights]
        H_before = -sum(p * math.log2(p) for p in probs if p > 0)
        H_after = 0.0
        return H_after - H_before

    def retrieve_with_summary(self, query: str, max_results: int = 5) -> List:
        """Retrieve with semantic_summary expansion."""
        results = self._lm.retrieve(query, max_results=max_results)
        matching_summaries = []
        for s in self._lm.semantic:
            if s.get("memory_type") == "semantic_summary":
                if query in s.get("content", "") or query in s.get("tags", []):
                    s["last_access_tick"] = self._tick
                    matching_summaries.append(s)
        if matching_summaries:
            for i in range(min(2, len(matching_summaries))):
                if matching_summaries[i] not in results:
                    results.insert(i, matching_summaries[i])
            self._metrics.retrieval_hit_rate = 1.0
        else:
            self._metrics.retrieval_hit_rate = 0.0
        return results[:max_results]

    def get_metrics(self) -> Dict:
        return {
            "compaction_count": self._metrics.compaction_count,
            "total_memories_compacted": self._metrics.total_memories_compacted,
            "total_summaries_created": self._metrics.total_summaries_created,
            "avg_compression_ratio": self._metrics.avg_compression_ratio,
            "max_compression_ratio": self._metrics.max_compression_ratio,
            "avg_entropy_delta": self._metrics.avg_entropy_delta,
            "retrieval_hit_rate": self._metrics.retrieval_hit_rate,
            "cross_topic_merge_count": self._metrics.cross_topic_merge_count,
            "same_topic_merge_count": self._metrics.same_topic_merge_count,
            "cross_topic_merge_rate": self._metrics.cross_topic_merge_rate,
            "semantic_purity": self._metrics.semantic_purity,
            "empty_summary_count": self._metrics.empty_summary_count,
            "empty_summary_rate": self._metrics.empty_summary_rate,
            "topology_fragmentation": self._metrics.topology_fragmentation,
            "topic_summary_counts": dict(self._metrics.topic_summary_counts),
            # PHASE_VI: coaccess graph health
            "coaccess_edge_count": self._coaccess.get_edge_count(),
            "coaccess_decay_factor": self._coaccess.DECAY_FACTOR,
            "coaccess_max_edges_per_node": self._coaccess.MAX_EDGES_PER_NODE,
            "coaccess_global_cap": self._coaccess.MAX_TOTAL_EDGES,
            # PHASE_VII: Tombstone lifecycle
            "tombstone_count": self._tombstone_count,
            "purge_count": self._purge_count,
            "active_tombstones": len(self._tombstones),
            "purge_delay": self.PURGE_DELAY,
        }

    def get_compaction_history(self) -> List[Dict]:
        return list(self._compaction_history)


# ── Semantic Compaction Runtime (wraps LayeredMemory) ─────────────────────────

class CompactionRuntime:
    """
    LayeredMemory + SemanticCompaction.
    Same external API as LayeredMemory.
    """
    def __init__(self, root: str):
        self._root = root
        self._lm = LayeredMemory(root)
        self._compaction = SemanticCompaction(self._lm, wal_manager=self._lm._wal)
        self._tick: int = 0
        self._retrieval_count: int = 0

    def tick(self) -> None:
        self._tick += 1
        self._compaction.tick(self._tick)
        self._lm.process_decay_buffer(self._tick)
        if self._tick % 50 == 0:
            self._lm.incremental_review(self._tick)
        if self._tick % 200 == 0:
            self._lm.try_flush(self._tick)
            self._compaction.run_compaction()

    def store(self, content: str, memory_type: str = "general",
               importance: float = 0.5, tags=None, current_tick: int = 0) -> str:
        return self._lm.store(content, memory_type=memory_type, importance=importance,
                             tags=tags or [], current_tick=current_tick or self._tick)

    def retrieve(self, query: str, current_goal: str = "", current_tick: int = 0,
                 max_results: int = 5) -> List:
        results = self._lm.retrieve(query, current_goal=current_goal,
                                    current_tick=current_tick or self._tick,
                                    max_results=max_results)
        tick = current_tick or self._tick
        # Filter out tombstoned/purged items — they must never be returned.
        # This is the last line of defense for G3 semantic integrity.
        results = [r for r in results
                   if isinstance(r, dict)
                   and not self._compaction.is_tombstoned(r.get("id", ""))]
        for r in results:
            if isinstance(r, dict):
                self._compaction.record_access(r.get("id", ""), tick)
        self._retrieval_count += 1
        return results

    def get_compaction_metrics(self) -> Dict:
        return self._compaction.get_metrics()

    @property
    def working(self): return self._lm.working
    @property
    def episodic(self): return self._lm.episodic
    @property
    def semantic(self): return self._lm.semantic
    @property
    def archive(self): return self._lm.archive
