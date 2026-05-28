"""
memory_retriever.py -- MCR Memory Retriever

High-level retrieval API for the cognitive loop.
Wraps MemoryIndex with a simple interface:

    retriever = MemoryRetriever(engine)
    memories = retriever.retrieve("task deadline approaching", limit=3)

Supports:
    - Keyword search over memory content
    - Tier filtering (working/episodic/semantic/archive)
    - Recency + frequency ranking
    - Co-access graph traversal
    - Auto-rebuild on state changes
"""
from typing import Any, Dict, List, Optional

from .memory_index import MemoryIndex


class MemoryRetriever:
    """
    Retrieval API for MCR runtime.

    Usage:
        retriever = MemoryRetriever(engine)
        # Query by text
        results = retriever.retrieve("project deadline", tier="episodic")
        # Get recent memories
        recent = retriever.recent(limit=5)
        # Find related memories
        related = retriever.related("mem-001")
    """

    def __init__(self, engine=None):
        self._engine = engine
        self._index: Optional[MemoryIndex] = None
        self._last_rebuild_tick = -1

    def _ensure_index(self):
        """Rebuild index if state has changed since last build."""
        if self._engine is None:
            return
        state = self._engine.get_state()
        current_tick = getattr(state, 'tick', 0)
        if self._index is None or current_tick != self._last_rebuild_tick:
            self._index = MemoryIndex(state)
            self._last_rebuild_tick = current_tick

    def retrieve(
        self,
        query: str,
        tier: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search memories by keyword query.

        Args:
            query: Search text (keywords, phrases)
            tier: Filter by memory tier (None = all tiers)
            limit: Max results to return
            min_score: Minimum relevance score (0.0 = no filter)

        Returns:
            List of {memory_id, content, tier, score, access_count, ...}
        """
        self._ensure_index()
        if self._index is None:
            return []
        return self._index.query(query, tier=tier, limit=limit, min_score=min_score)

    def recent(self, tier: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recently accessed memories."""
        self._ensure_index()
        if self._index is None:
            return []
        return self._index._recent_memories(tier, limit)

    def related(self, memory_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get memories co-accessed with the given memory."""
        self._ensure_index()
        if self._index is None:
            return []
        return self._index.get_related(memory_id, limit)

    def context_for(
        self,
        query: str,
        max_tokens: int = 500,
        tier: Optional[str] = None,
    ) -> str:
        """
        Build a text context block from relevant memories.
        Used by cognitive loop to inject memory into LLM prompts.

        Returns formatted string like:
            [MEMORY] content1 (episodic, accessed 3x)
            [MEMORY] content2 (working, accessed 1x)
        """
        results = self.retrieve(query, tier=tier, limit=10)
        lines = []
        token_budget = max_tokens
        for r in results:
            content = r['content']
            tier_label = r['tier']
            access_count = r['access_count']
            line = f"[{tier_label.upper()}] {content} (accessed {access_count}x)"
            # Rough token estimate: 1 token ~= 4 chars
            line_tokens = len(line) // 4
            if line_tokens > token_budget:
                break
            lines.append(line)
            token_budget -= line_tokens
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        """Index statistics."""
        self._ensure_index()
        if self._index is None:
            return {"total_memories": 0}
        return self._index.stats()
