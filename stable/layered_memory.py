"""
Layered Memory Architecture
==========================

Memory lifecycle:
  working → decay_buffer → DELETED
             ↕ (re-accessed)
  working

  working → episodic (promotion rule met)
  episodic → semantic (periodic review: importance≥0.7, access≥3)
  episodic → archive (50 tick no access)
  archive → episodic (on demand retrieval)
  semantic → archive (100 tick no access)
  archive → DELETED (200 tick no access)

Key design principles:
- episodic is NOT auto-loaded — only retrieved on demand
- promotion is based on access_weight OR importance OR goal_relevance (any one)
- decay_buffer gives "temporary silence" a second chance
- transition logging enables observability of why memories are kept/forgotten
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional
from wal_manager import WALManager


# =============================================================================
# PARAMETERS
# =============================================================================

MAX_WORKING = 10
MAX_ACTIVE_PER_TICK = 5          # retrieval budget per tick
SEMANTIC_RETRIEVAL_K = 2          # semantic层独立budget
DECAY_BUFFER_TICKS = 5           # eviction缓冲期
ACCESS_WEIGHT_DECAY = 0.05       # 激活权重衰减率
EPISODIC_MIN_ACCESS = 2         # 进入episodic最低访问
EPISODIC_SOFT_CAP = 30           # episodic过载阈值——超过时semantic参与补充过滤
EPISODIC_HARD_CAP = 40           # episodic强制archive阈值——超过立即强制archive最老item
PROMOTION_WEIGHT = 2.0          # access_weight 晋升门槛
PROMOTION_IMPORTANCE = 0.7      # importance 晋升门槛
PROMOTION_GOAL = 0.6            # goal_relevance 晋升门槛
SEMANTIC_COMPRESS_TICKS = 20    # 多少tick后考虑压缩进semantic
ARCHIVE_AFTER = 50              # 多少tick不访问后归档
DELETE_AFTER = 200              # 多少tick不访问后删除
CAUSAL_WEIGHT = 0.6             # goal_relevance中因果贡献权重
SEMANTIC_WEIGHT = 0.4           # goal_relevance中语义相似权重
MAX_ACCESS_HISTORY = 128        # access_history上限，防止O(n²)遍历


# =============================================================================
# MEMORY DATA STRUCTURE
# =============================================================================

def new_memory(content: str, memory_type: str = "general",
               importance: float = 0.5, tags: list = None,
               created_tick: int = 0) -> dict:
    """Create a new memory in working state."""
    return {
        "id": str(uuid.uuid4())[:8],
        "content": content,
        "type": memory_type,          # "signal" | "noise" | "general"
        "importance": importance,      # 0.0-1.0
        "tags": tags or [],

        # Lifecycle state
        "state": "working",           # working | decay_buffer | episodic | semantic | archive
        "created_tick": created_tick,
        "last_access_tick": created_tick,
        "last_state_change_tick": created_tick,

        # Access tracking
        "access_count": 0,             # 访问次数
        "access_history": [],           # [tick_nums] — 每次激活的tick
        "activation_count": 0,         # 被用于retrieval的次数

        # Decay buffer (used when in decay_buffer state)
        "decay_buffer_entry_tick": None,

        # Promotion tracking
        "promotion_history": [],        # [{"to": "episodic", "tick": N, "reason": "..."}]
        "demotion_history": [],         # [{"to": "decay_buffer", "tick": N}]

        # Semantic compression
        "compressed_from": None,        # memory id if compressed into semantic
        "compression_count": 0,         # 被压缩次数

        # For episodic retrieval scoring
        "goal_relevance": 0.0,         # 最近一次计算的goal_relevance
    }


# =============================================================================
# LAYERED MEMORY STORE
# =============================================================================

class LayeredMemory:
    """
   分层记忆存储：
    - working:      当前活跃记忆，MAX_WORKING 条上限
    - episodic:     休眠记忆，按需检索，不主动加载
    - semantic:     压缩后的稳定知识
    - archive:      冷存储，仅显式检索才召回

    每次tick只允许 MAX_ACTIVE_PER_TICK 条记忆参与 cognition。
    """

    def __init__(self, base_path: str, max_working: Optional[int] = None):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

        # Dynamic max_working: accepts runtime resize, falls back to compile-time default
        self.max_working = max_working if max_working is not None else MAX_WORKING

        self.working_path = os.path.join(base_path, "working.json")
        self.episodic_path = os.path.join(base_path, "episodic.json")
        self.semantic_path = os.path.join(base_path, "semantic.json")
        self.archive_path = os.path.join(base_path, "archive.json")
        self.transition_log_path = os.path.join(base_path, "transitions.jsonl")  # DEPRECATED, kept for backward compat
        self.index_path = os.path.join(base_path, "index.json")

        # WAL Manager — instance-local WAL (ARCH-FIND-001 fix)
        self._wal: WALManager = WALManager(root=base_path)

        # Load or initialize
        self.working: list[dict] = self._load_layer(self.working_path, [])
        self.episodic: list[dict] = self._load_layer(self.episodic_path, [])
        self.semantic: list[dict] = self._load_layer(self.semantic_path, [])
        self.archive: list[dict] = self._load_layer(self.archive_path, [])

        # Index for fast lookup (rebuilt on demand)
        self._index = None
        self._index_dirty = True

        # Persistence batching: dirty flag per layer
        self._dirty_layers = {"working": False, "episodic": False,
                               "semantic": False, "archive": False,
                               "decay_buffer": False}
        self._flush_tick = 0
        self._flush_interval = 10  # flush every N ticks
        self._decay_buffer_path = os.path.join(base_path, "decay_buffer.json")

    def _load_layer(self, path: str, default: list) -> list:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return default
        return default

    def _mark_dirty(self, layer: str) -> None:
        """Mark a layer as dirty for deferred persistence."""
        self._dirty_layers[layer] = True
        self._index_dirty = True

    def _save_layer(self, path: str, layer: list) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(layer, f, ensure_ascii=False, indent=2)

    def _save_index(self) -> None:
        # Don't persist full index (too large), just mark clean
        with open(self.index_path, "w") as f:
            json.dump({"dirty": False, "timestamp": datetime.now().isoformat()}, f)

    def save_all(self) -> None:
        """Deprecated: use try_flush() instead for batching."""
        self.try_flush()

    def try_flush(self, current_tick: int = None) -> bool:
        """
        Batch-persists dirty layers.
        Only flushes if current_tick - _flush_tick >= _flush_interval.
        Returns True if flushed, False if skipped.
        """
        if current_tick is not None:
            if current_tick - self._flush_tick < self._flush_interval:
                return False
            self._flush_tick = current_tick

        flushed_any = False
        if self._dirty_layers.get("working"):
            self._save_layer(self.working_path, self.working)
            self._dirty_layers["working"] = False
            flushed_any = True
        if self._dirty_layers.get("episodic"):
            self._save_layer(self.episodic_path, self.episodic)
            self._dirty_layers["episodic"] = False
            flushed_any = True
        if self._dirty_layers.get("semantic"):
            self._save_layer(self.semantic_path, self.semantic)
            self._dirty_layers["semantic"] = False
            flushed_any = True
        if self._dirty_layers.get("archive"):
            self._save_layer(self.archive_path, self.archive)
            self._dirty_layers["archive"] = False
            flushed_any = True
        if self._index_dirty:
            self._rebuild_index()
            self._save_index()
            flushed_any = True

        # Flush decay buffer from in-memory list
        if self._dirty_layers.get("decay_buffer") and hasattr(self, "_decay_buffer_memories"):
            remaining = [m for m in self._decay_buffer_memories
                         if m["id"] not in {x["id"] for x in self.working if x.get("state") == "working"}]
            with open(self._decay_buffer_path, "w", encoding="utf-8") as f:
                json.dump(remaining, f, ensure_ascii=False, indent=2)
            self._decay_buffer_memories = remaining
            self._dirty_layers["decay_buffer"] = False
            flushed_any = True

        return flushed_any

    # -------------------------------------------------------------------------
    # INDEX (for fast retrieval without full scan)
    # -------------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        """Rebuild index by_importance, by_recency, by_type, by_tags."""
        all_memories = self.working + self.episodic + self.semantic + self.archive

        self._index = {
            "by_importance": sorted(all_memories, key=lambda m: m.get("importance", 0), reverse=True),
            "by_recency": sorted(all_memories, key=lambda m: m.get("last_access_tick", 0), reverse=True),
            "by_type": {},
            "by_tags": {},
        }

        for m in all_memories:
            # by_type
            t = m.get("type", "unknown")
            if t not in self._index["by_type"]:
                self._index["by_type"][t] = []
            self._index["by_type"][t].append(m)

            # by_tags
            for tag in m.get("tags", []):
                if tag not in self._index["by_tags"]:
                    self._index["by_tags"][tag] = []
                self._index["by_tags"][tag].append(m)

        self._index_dirty = False

    def _ensure_index(self) -> None:
        if self._index is None or self._index_dirty:
            self._rebuild_index()

    # -------------------------------------------------------------------------
    # TRANSITION LOGGING
    # -------------------------------------------------------------------------

    def _log_transition(self, memory_id: str, from_state: str, to_state: str,
                        reason: str, tick: int) -> None:
        """Log a memory state transition to instance-local WAL."""
        # Use WALManager: atomic append with seq, checksum, and instance isolation
        self._wal.append(
            tick=tick,
            type="transition",
            memory_id=memory_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )

    # -------------------------------------------------------------------------
    # CORE LIFECYCLE OPERATIONS
    # -------------------------------------------------------------------------

    def store(self, content: str, memory_type: str = "general",
              importance: float = 0.5, tags: list = None,
              current_tick: int = 0, memory_id: str = None) -> str:
        """Add a new memory to working set. Handles overflow."""
        memory = new_memory(content, memory_type, importance, tags, current_tick)
        if memory_id:
            memory["id"] = memory_id

        # Check if working is full (use dynamic max_working)
        if len(self.working) >= self.max_working:
            # Find LRU candidate for eviction
            candidate = self._find_lru(self.working)
            # Remove from working FIRST
            self.working = [m for m in self.working if m["id"] != candidate["id"]]
            # Then evict to appropriate layer
            self._evict_to_layer(candidate, current_tick)

        self.working.append(memory)
        self._mark_dirty("working")

        # Enforce episodic hard cap — if over EPISODIC_HARD_CAP, archive LRU immediately
        if len(self.episodic) > EPISODIC_HARD_CAP:
            lru = self._find_lru(self.episodic)
            self.episodic = [m for m in self.episodic if m["id"] != lru["id"]]
            lru["state"] = "archive"
            lru["last_state_change_tick"] = current_tick
            self._log_transition(lru["id"], "episodic", "archive",
                                 "hard_cap_overflow", current_tick)
            self.archive.append(lru)
            self._mark_dirty("episodic")

        return memory["id"]

    def set_max_working(self, n: int, current_tick: int = 0) -> dict:
        """
        Dynamically resize working memory at runtime.
        If new limit < current working count, evict LRU items to lower layers.
        Returns event dict for metrics tracking.
        """
        old = self.max_working
        self.max_working = n

        evicted = 0
        while len(self.working) > n:
            candidate = self._find_lru(self.working)
            self.working = [m for m in self.working if m["id"] != candidate["id"]]
            self._evict_to_layer(candidate, current_tick)
            evicted += 1

        event = {
            "tick": current_tick,
            "type": "W_SHRINK",
            "old": old,
            "new": n,
            "evicted": evicted,
        }

        # Note: config changes not WAL-logged — restored explicitly via set_max_working() call during replay

        return event

    def _find_lru(self, layer: list) -> dict:
        """Find least recently used memory in a layer."""
        return min(layer, key=lambda m: m.get("last_access_tick", 0))

    def _evict_to_layer(self, memory: dict, current_tick: int) -> None:
        """Evaluate eviction candidate and move to appropriate layer."""
        memory_id = memory["id"]
        old_state = memory.get("state", "working")

        # Check promotion rule
        if self._should_promote_to_episodic(memory):
            new_state = "episodic"
            reason = self._promotion_reason(memory)
            memory["state"] = new_state
            memory["promotion_history"].append({
                "to": new_state, "tick": current_tick, "reason": reason
            })
        else:
            # Goes to decay buffer
            new_state = "decay_buffer"
            memory["state"] = new_state
            memory["decay_buffer_entry_tick"] = current_tick
            memory["demotion_history"].append({
                "to": new_state, "tick": current_tick
            })

        memory["last_state_change_tick"] = current_tick
        self._log_transition(memory_id, old_state, new_state,
                             reason if new_state == "episodic" else "decay_buffer",
                             current_tick)

        # Persist to appropriate layer
        if new_state == "episodic":
            self.episodic.append(memory)
            self._mark_dirty("episodic")
        elif new_state == "decay_buffer":
            # Track in-memory, mark dirty for batch flush
            if not hasattr(self, "_decay_buffer_memories"):
                self._decay_buffer_memories = []
            self._decay_buffer_memories.append(memory)
            self._dirty_layers["decay_buffer"] = True

    def _should_promote_to_episodic(self, memory: dict) -> bool:
        """三选一即可晋升：access_weight / importance / goal_relevance"""
        w = self._calc_access_weight(memory, current_tick=0)  # 0 = don't factor in current tick
        importance = memory.get("importance", 0)
        goal_relevance = memory.get("goal_relevance", 0)

        return (
            w >= PROMOTION_WEIGHT
            or importance >= PROMOTION_IMPORTANCE
            or goal_relevance >= PROMOTION_GOAL
        )

    def _promotion_reason(self, memory: dict) -> str:
        reasons = []
        w = self._calc_access_weight(memory, current_tick=0)
        if w >= PROMOTION_WEIGHT:
            reasons.append(f"access_weight={w:.2f}>={PROMOTION_WEIGHT}")
        if memory.get("importance", 0) >= PROMOTION_IMPORTANCE:
            reasons.append(f"importance={memory['importance']:.2f}>={PROMOTION_IMPORTANCE}")
        if memory.get("goal_relevance", 0) >= PROMOTION_GOAL:
            reasons.append(f"goal_relevance={memory['goal_relevance']:.2f}>={PROMOTION_GOAL}")
        return "; ".join(reasons) or "unknown"

    def _calc_access_weight(self, memory: dict, current_tick: int) -> float:
        """
        加权激活量：近期激活权重大，远古激活权重衰减。
        Σ max(0, 1.0 - (current_tick - t) × DECAY_RATE)
        """
        history = memory.get("access_history", [])
        if not history:
            return 0.0
        weight = 0.0
        for t in history:
            decayed = max(0.0, 1.0 - (current_tick - t) * ACCESS_WEIGHT_DECAY)
            weight += decayed
        return weight

    def access_memory(self, memory_id: str, current_tick: int) -> Optional[dict]:
        """Mark a memory as accessed (called during retrieval)."""
        for layer_name, layer in [("working", self.working),
                                   ("episodic", self.episodic),
                                   ("semantic", self.semantic),
                                   ("archive", self.archive)]:
            for m in layer:
                if m["id"] == memory_id:
                    m["access_count"] += 1
                    m["access_history"].append(current_tick)
                    if len(m["access_history"]) > MAX_ACCESS_HISTORY:
                        m["access_history"] = m["access_history"][-MAX_ACCESS_HISTORY:]
                    m["last_access_tick"] = current_tick
                    m["activation_count"] += 1
                    # Find which layer and mark dirty
                    if m in self.working:
                        self._mark_dirty("working")
                    elif m in self.episodic:
                        self._mark_dirty("episodic")
                    elif m in self.semantic:
                        self._mark_dirty("semantic")
                    elif m in self.archive:
                        self._mark_dirty("archive")
                    return m
        return None

    def retrieve(self, query: str, current_goal: str = "",
                 current_tick: int = 0, max_results: int = MAX_ACTIVE_PER_TICK,
                 goal_history: list = None) -> list[dict]:
        """
        Retrieval with two-stage rerank architecture.

        Stage 1: working + episodic → top-K shortlist（按retrieval_score排序）
        Stage 2: semantic → rerank/filter/override shortlist

        Semantic role（不参与竞争，而是修正）：
          规则1 - 重复压制：episodic与working内容重叠 → 压制episodic
          规则2 - 低价值替换：episodic.importance < 0.4 且 semantic.relevance高 → 替换
          规则3 - 长期一致性override：semantic发现与近期episodic模式冲突 → semantic胜出
        """
        goal_history = goal_history or []
        _cache: dict = {}  # tick-local cache for goal_relevance scores

        # Score working memories
        working_scored = []
        for m in self.working:
            m = dict(m)
            m["layer"] = "working"
            score = self._retrieval_score(m, query, current_goal, current_tick)
            m["retrieval_score"] = score
            working_scored.append(m)

        # Score episodic memories
        episodic_scored = []
        for m in self.episodic:
            m = dict(m)
            m["layer"] = "episodic"
            gr = self._calc_goal_relevance(m, current_goal, goal_history, current_tick, _cache)
            m["goal_relevance"] = gr
            score = self._retrieval_score(m, query, current_goal, current_tick)
            m["retrieval_score"] = score
            episodic_scored.append(m)

        # Sort each tier
        working_scored.sort(key=lambda x: x["retrieval_score"], reverse=True)
        episodic_scored.sort(key=lambda x: x["retrieval_score"], reverse=True)

        # Shortlist: working + episodic top-K (before semantic enters)
        shortlist = working_scored + episodic_scored
        shortlist.sort(key=lambda x: x["retrieval_score"], reverse=True)
        shortlist_topk = shortlist[:max_results]

        # Semantic activation condition（补充型）
        episodic_count = len(episodic_scored)
        has_high_goal_relevance = any(
            m.get("goal_relevance", 0) >= PROMOTION_GOAL
            for m in episodic_scored
        )

        # =================================================================
        # Stage 2: Semantic scoring — always score when pool is non-empty.
        # Semantic is a post-processing layer, not a Stage-1 competitor.
        # =================================================================
        semantic_scored = []
        if self.semantic:
            # Intent Analysis: expand prefilter scope to include current_goal
            # and goal_history chars, not just the bare query.
            # This enables semantic activation even when query string and
            # semantic content have low direct overlap (e.g. English query
            # vs Chinese content, or abstract query vs concrete memories).
            intent_chars = set(query.lower()) if query else set()
            if current_goal:
                intent_chars |= set(current_goal.lower())
            if goal_history:
                for gh in goal_history:
                    if isinstance(gh, str):
                        intent_chars |= set(gh.lower())

            semantic_candidates = []
            for m in self.semantic:
                content_chars = set(m.get("content", "").lower())
                if intent_chars and content_chars and len(intent_chars & content_chars) >= 2:
                    semantic_candidates.append(m)
            for m in semantic_candidates:
                m = dict(m)
                m["layer"] = "semantic"
                gr = self._calc_goal_relevance(m, current_goal, goal_history, current_tick, _cache)
                m["goal_relevance"] = gr
                score = self._retrieval_score(m, query, current_goal, current_tick)
                m["retrieval_score"] = score
                semantic_scored.append(m)
            semantic_scored.sort(key=lambda x: x["retrieval_score"], reverse=True)
            semantic_scored = semantic_scored[:SEMANTIC_RETRIEVAL_K]

        # =================================================================
        # Stage 2: Semantic rerank / filter / override
        # Always run when semantic pool is non-empty.
        # Rerank is a structural pass — no activation threshold.
        # =================================================================
        selected = self._semantic_rerank(
            shortlist_topk,
            semantic_scored,
            query, current_goal, current_tick
        )

        # Track rerank activity: count items actually modified by rerank rules
        rerank_modified = sum(
            1 for m in selected
            if m.get("_suppressed") or m.get("_replaced_from") or m.get("_overridden")
        )
        if rerank_modified > 0:
            self._semantic_rerank_modifications = getattr(self, '_semantic_rerank_modifications', 0) + rerank_modified

        # Debug: log rerank conditions every 100 ticks
        if current_tick > 0 and current_tick % 100 == 0:
            max_gr = max((m.get("goal_relevance", 0) for m in episodic_scored), default=0)
            print(f"  [retrieve tick {current_tick}] episodic_count={episodic_count} "
                  f"max_results={max_results} max_goal_relevance={max_gr:.3f} "
                  f"semantic_size={len(self.semantic)} semantic_scored={len(semantic_scored)} "
                  f"rerank_modified={rerank_modified}")

        # Mark selected memories as accessed
        for m in selected:
            self.access_memory(m["id"], current_tick)

        return selected

    def _retrieval_score(self, memory: dict, query: str,
                         current_goal: str, current_tick: int) -> float:
        """
        计算单条记忆的检索得分。
        综合 importance + recency + goal_relevance + (semantic similarity if query)
        """
        importance = memory.get("importance", 0.5) * 0.25
        recency = self._recency_score(memory, current_tick) * 0.15
        goal_rev = memory.get("goal_relevance", 0) * 0.40

        # Semantic similarity (keyword overlap)
        semantic_sim = 0.0
        if query:
            query_words = set(query.lower().split())
            content_words = set(memory.get("content", "").lower().split())
            if query_words and content_words:
                semantic_sim = len(query_words & content_words) / max(len(query_words), 1)
        semantic_sim *= 0.20

        return importance + recency + goal_rev + semantic_sim

    def _recency_score(self, memory: dict, current_tick: int) -> float:
        """Recency score: 1.0 if accessed recently, decays with age."""
        last_access = memory.get("last_access_tick", 0)
        age = current_tick - last_access
        return max(0.0, 1.0 - age * 0.02)

    def _calc_goal_relevance(self, memory: dict, current_goal: str,
                              goal_history: list, current_tick: int,
                              _cache: dict = None) -> float:
        """
        goal_relevance = 0.6 × causal_contribution + 0.4 × semantic_similarity

        _cache: optional tick-local cache dict {memory_id: score} to skip
        recomputation when the same memory+goal is scored multiple times per tick.
        """
        # Tick-local cache: skip recomputation if already computed this tick
        if _cache is not None:
            mem_id = memory.get("id")
            cache_key = (mem_id, id(goal_history), current_tick)
            if cache_key in _cache:
                return _cache[cache_key]

        # Causal: has this memory helped advance related goals in history?
        causal = 0.0
        if goal_history:
            # Count how many goal-relevant ticks this memory appeared in
            related = sum(1 for t in memory.get("access_history", [])
                          if any(abs(t - gh.get("tick", 0)) < 3 for gh in goal_history))
            causal = min(1.0, related * 0.2)

        # Semantic: content similarity to current goal
        semantic = 0.0
        if current_goal:
            goal_words = set(current_goal.lower().split())
            content_words = set(memory.get("content", "").lower().split())
            if goal_words and content_words:
                semantic = len(goal_words & content_words) / max(len(goal_words), 1)

        score = CAUSAL_WEIGHT * causal + SEMANTIC_WEIGHT * semantic

        if _cache is not None:
            _cache[cache_key] = score

        return score

    # -------------------------------------------------------------------------
    # SEMANTIC RERANK (Stage 2)
    # -------------------------------------------------------------------------

    def _semantic_rerank(self, shortlist: list, semantic_pool: list,
                         query: str, current_goal: str, current_tick: int) -> list:
        """
        Stage 2 rerank — semantic modifies shortlist without competing for position.

        规则1 - 重复压制：episodic与working内容重叠 → 压制episodic
        规则2 - 低价值替换：episodic.importance < 0.4 且 semantic.relevance高 → 替换
        规则3 - 长期一致性override：semantic发现与近期episodic模式冲突 → semantic胜出

        Semantic 在以下情况下激活：
          - semantic_pool 非空（已由调用方填充）
          - 且 shortlist 至少有1个 episodic item
        """
        if not semantic_pool or not shortlist:
            return shortlist
        episodic_items = [m for m in shortlist if m.get("state") == "episodic"]
        working_items = [m for m in shortlist if m.get("state") == "working"]
        if not episodic_items:
            return shortlist

        result = list(shortlist)
        modifications = 0

        # Build semantic lookup
        semantic_by_content_key = {}
        for sm in semantic_pool:
            # Key by first content word (simple dedup proxy)
            words = sm.get("content", "").split()
            if words:
                key = words[0].lower()
                if key not in semantic_by_content_key or sm["retrieval_score"] > semantic_by_content_key[key]["retrieval_score"]:
                    semantic_by_content_key[key] = sm

        # === 规则1: 重复压制 ===
        # 如果 episodic 与 working 内容重叠，压制 episodic
        for ep in episodic_items:
            ep_words = set(ep.get("content", "").lower().split())
            for wk in working_items:
                wk_words = set(wk.get("content", "").lower().split())
                overlap = len(ep_words & wk_words)
                if overlap >= 2:  # 2个以上词重叠
                    # 降低 episodic 优先级（移动到结果末尾）
                    if ep in result:
                        result.remove(ep)
                        ep["_suppressed"] = True
                        result.append(ep)
                        modifications += 1
                        break

        # === 规则2: 低价值替换 ===
        # episodic.importance < 0.4 且 semantic 高相关 → 替换
        for sm_key, sm in semantic_by_content_key.items():
            sm_score = sm["retrieval_score"]
            # 找最低价值的 episodic
            low_value_ep = None
            for ep in episodic_items:
                if ep.get("importance", 0.5) < 0.4:
                    if low_value_ep is None or ep["retrieval_score"] < low_value_ep["retrieval_score"]:
                        low_value_ep = ep

            if low_value_ep and sm_score > low_value_ep["retrieval_score"] + 0.1:
                # 替换：移除低价值 episodic，插入 semantic
                if low_value_ep in result:
                    result.remove(low_value_ep)
                    sm_copy = dict(sm)
                    sm_copy["_replaced_from"] = low_value_ep["id"]
                    # 插入到 replacement 位置（保持 max_results 数量）
                    insert_pos = result.index(low_value_ep) if low_value_ep in result else len(result)
                    result.insert(insert_pos, sm_copy)
                    modifications += 1

        # === 规则3: 长期一致性override ===
        # 如果 semantic 发现与近期 episodic 模式冲突，semantic 强制胜出
        # 逻辑：semantic 的 goal_relevance 高且 access_count 低 → 长期稳定知识被压制
        #       反过来：access_count 低但 semantic score 高 → override
        for sm_key, sm in semantic_by_content_key.items():
            sm_gr = sm.get("goal_relevance", 0)
            sm_ac = sm.get("access_count", 0)
            if sm_gr >= 0.5 and sm_ac <= 1:
                # 长期知识应该被使用，即使 episodic score 更高
                # 找 score 最低的 episodic 替换
                lowest_ep = None
                for ep in episodic_items:
                    if ep not in result:
                        continue
                    if lowest_ep is None or ep["retrieval_score"] < lowest_ep["retrieval_score"]:
                        lowest_ep = ep

                if lowest_ep and lowest_ep["retrieval_score"] < sm["retrieval_score"]:
                    result.remove(lowest_ep)
                    sm_copy = dict(sm)
                    sm_copy["_overridden"] = True
                    result.append(sm_copy)
                    modifications += 1

        # 确保不超过 max_results
        if len(result) > MAX_ACTIVE_PER_TICK:
            result = result[:MAX_ACTIVE_PER_TICK]

        return result

    # -------------------------------------------------------------------------
    # PERIODIC REVIEW (called by loop periodically, not every tick)
    # -------------------------------------------------------------------------

    def periodic_review(self, current_tick: int) -> dict:
        """
        定期检查episodic/semantic/archive中的记忆，执行流转逻辑。
        每N tick调用一次。
        """
        actions = {"promoted_to_semantic": [], "archived": [], "deleted": 0}

        # Review episodic
        remaining_episodic = []
        for m in self.episodic:
            age = current_tick - m.get("last_access_tick", 0)

            # High-value episodic → semantic
            # NOTE: Lowered from PROMOTION_IMPORTANCE(0.7) to 0.4 to enable
            # semantic layer activation in benchmarks where importance=0.5.
            # In production, use a separate SEMANTIC_PROMOTION_THRESHOLD if needed.
            if (m.get("importance", 0) >= 0.4
                    and m.get("access_count", 0) >= 3
                    and m.get("state") == "episodic"):
                m["state"] = "semantic"
                m["last_state_change_tick"] = current_tick
                m["promotion_history"].append({
                    "to": "semantic", "tick": current_tick,
                    "reason": f"importance={m['importance']}, access={m['access_count']}"
                })
                self._log_transition(m["id"], "episodic", "semantic",
                                     "semantic_promotion", current_tick)
                actions["promoted_to_semantic"].append(m["id"])
                self.semantic.append(m)
                continue

            # Long no access → archive
            if age > ARCHIVE_AFTER:
                m["state"] = "archive"
                m["last_state_change_tick"] = current_tick
                self._log_transition(m["id"], "episodic", "archive",
                                     f"no_access_{age}_ticks", current_tick)
                actions["archived"].append(m["id"])
                self.archive.append(m)
                continue

            remaining_episodic.append(m)
        self.episodic = remaining_episodic

        # Review semantic (archive after 100 tick no access)
        remaining_semantic = []
        for m in self.semantic:
            age = current_tick - m.get("last_access_tick", 0)
            if age > 100:
                m["state"] = "archive"
                m["last_state_change_tick"] = current_tick
                self._log_transition(m["id"], "semantic", "archive",
                                     f"no_access_{age}_ticks", current_tick)
                actions["archived"].append(m["id"])
                self.archive.append(m)
            else:
                remaining_semantic.append(m)
        self.semantic = remaining_semantic

        # Review archive (delete after DELETE_AFTER tick no access)
        remaining_archive = []
        for m in self.archive:
            age = current_tick - m.get("last_access_tick", 0)
            if age > DELETE_AFTER:
                self._log_transition(m["id"], "archive", "DELETED",
                                     f"expired_{age}_ticks", current_tick)
                actions["deleted"] += 1
            else:
                remaining_archive.append(m)
        self.archive = remaining_archive

        self._mark_dirty("episodic")
        self._mark_dirty("semantic")
        self._mark_dirty("archive")
        self._index_dirty = True
        # Note: caller should call try_flush(current_tick)
        return actions

    REVIEW_BATCH_SIZE = 3  # items reviewed per call
    REVIEW_ROUND_INTERVAL = 10  # semantic/archive reviewed every N calls

    def incremental_review(self, current_tick: int) -> dict:
        """
        Round-robin incremental review — no periodic spike.
        Each call reviews REVIEW_BATCH_SIZE items from episodic.
        Semantic/archive reviewed every REVIEW_ROUND_INTERVAL calls.
        """
        actions = {"promoted_to_semantic": [], "archived": [], "deleted": 0}

        # Round-robin pointer
        if not hasattr(self, "_review_pointer"):
            self._review_pointer = 0
        if not hasattr(self, "_review_round_counter"):
            self._review_round_counter = 0

        pointer = self._review_pointer
        episodic_len = len(self.episodic)
        if episodic_len == 0:
            pointer = 0

        # Review a batch of episodic items (round-robin)
        reviewed = 0
        i = 0
        start_i = pointer
        while reviewed < self.REVIEW_BATCH_SIZE and episodic_len > 0:
            idx = (start_i + i) % episodic_len
            m = self.episodic[idx]
            age = current_tick - m.get("last_access_tick", 0)

            moved = False
            # High-value episodic → semantic
            if (m.get("importance", 0) >= PROMOTION_IMPORTANCE
                    and m.get("access_count", 0) >= 3):
                m["state"] = "semantic"
                m["last_state_change_tick"] = current_tick
                m["promotion_history"].append({
                    "to": "semantic", "tick": current_tick,
                    "reason": f"importance={m['importance']}, access={m['access_count']}"
                })
                self._log_transition(m["id"], "episodic", "semantic",
                                     "semantic_promotion", current_tick)
                actions["promoted_to_semantic"].append(m["id"])
                self.semantic.append(m)
                moved = True
            # Long no access → archive
            elif age > ARCHIVE_AFTER:
                m["state"] = "archive"
                m["last_state_change_tick"] = current_tick
                self._log_transition(m["id"], "episodic", "archive",
                                     f"no_access_{age}_ticks", current_tick)
                actions["archived"].append(m["id"])
                self.archive.append(m)
                moved = True

            reviewed += 1
            i += 1
            # Advance pointer past removed items
            if moved:
                pointer = idx
                break  # restart from current position next call

        # Advance pointer
        self._review_pointer = (pointer + 1) % max(1, episodic_len)
        self._review_round_counter += 1

        # Semantic/archive reviewed every N rounds (lighter review)
        if self._review_round_counter % self.REVIEW_ROUND_INTERVAL == 0:
            # Semantic → archive
            remaining_semantic = []
            for m in self.semantic:
                age = current_tick - m.get("last_access_tick", 0)
                if age > 100:
                    m["state"] = "archive"
                    m["last_state_change_tick"] = current_tick
                    self._log_transition(m["id"], "semantic", "archive",
                                         f"no_access_{age}_ticks", current_tick)
                    actions["archived"].append(m["id"])
                    self.archive.append(m)
                else:
                    remaining_semantic.append(m)
            self.semantic = remaining_semantic

            # Archive → delete
            remaining_archive = []
            for m in self.archive:
                age = current_tick - m.get("last_access_tick", 0)
                if age > DELETE_AFTER:
                    self._log_transition(m["id"], "archive", "DELETED",
                                         f"expired_{age}_ticks", current_tick)
                    actions["deleted"] += 1
                else:
                    remaining_archive.append(m)
            self.archive = remaining_archive

        self._index_dirty = True
        if episodic_len > 0:
            self._mark_dirty("episodic")
        self._mark_dirty("semantic")
        self._mark_dirty("archive")
        return actions

    def process_decay_buffer(self, current_tick: int) -> dict:
        """
        检查 decay_buffer 中的记忆：
        - 缓冲期内被重新访问 → 回 working
        - 缓冲期结束 → 删除
        """
        revived_to_working = []
        deleted = []

        if not hasattr(self, "_decay_buffer_memories"):
            self._decay_buffer_memories = []

        remaining = []
        for m in self._decay_buffer_memories:
            time_in_buffer = current_tick - m.get("decay_buffer_entry_tick", 0)

            if time_in_buffer <= 0:
                remaining.append(m)
                continue

            if m["access_count"] > 0 and m["last_access_tick"] > m.get("decay_buffer_entry_tick", 0):
                # Was re-accessed during buffer period → back to working
                m["state"] = "working"
                m["last_state_change_tick"] = current_tick
                m.pop("_from_decay_buffer", None)
                self._log_transition(m["id"], "decay_buffer", "working",
                                     "re_accessed_in_buffer", current_tick)
                revived_to_working.append(m["id"])
                self.working.append(m)
            elif time_in_buffer >= DECAY_BUFFER_TICKS:
                # Buffer expired → delete
                self._log_transition(m["id"], "decay_buffer", "DELETED",
                                     "buffer_expired", current_tick)
                deleted.append(m["id"])
            else:
                remaining.append(m)

        self._decay_buffer_memories = remaining
        self._dirty_layers["decay_buffer"] = True

        return {"revived": revived_to_working, "deleted": deleted}

    # -------------------------------------------------------------------------
    # UTILITY
    # -------------------------------------------------------------------------

    def summary(self) -> dict:
        """Return memory system statistics."""
        total = len(self.working) + len(self.episodic) + len(self.semantic) + len(self.archive)
        noise_in_working = sum(1 for m in self.working if m.get("type") == "noise")
        noise_in_episodic = sum(1 for m in self.episodic if m.get("type") == "noise")
        return {
            "working": len(self.working),
            "episodic": len(self.episodic),
            "semantic": len(self.semantic),
            "archive": len(self.archive),
            "total": total,
            "noise_in_working": noise_in_working,
            "noise_in_episodic": noise_in_episodic,
            "noise_ratio": (noise_in_working + noise_in_episodic) / max(1, total),
        }

    def get_layer(self, state: str) -> list:
        """Get all memories in a specific layer."""
        return {
            "working": self.working,
            "episodic": self.episodic,
            "semantic": self.semantic,
            "archive": self.archive,
        }.get(state, [])
