"""
memory_index.py -- MCR Memory Index

In-memory index over runtime state for fast memory retrieval.
Builds keyword, tier, and co-access indices from SystemState.

Usage:
    index = MemoryIndex(state)
    results = index.query("task deadline", tier="episodic", limit=5)

No external dependencies. Pure Python.
"""
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set


def _tokenize(text: str) -> Set[str]:
    """Split text into lowercase word tokens. Stops at 2+ chars."""
    return {w for w in re.split(r'\W+', text.lower()) if len(w) >= 2}


class MemoryIndex:
    """
    Query index over MCR runtime state.

    Builds inverted index from memory content for fast keyword search,
    tracks tier membership, access frequency, and recency.
    """

    def __init__(self, state=None):
        self._keyword_index: Dict[str, Set[str]] = defaultdict(set)
        self._tier_index: Dict[str, Set[str]] = defaultdict(set)
        self._memories: Dict[str, dict] = {}
        self._access_count: Dict[str, int] = defaultdict(int)
        self._last_access: Dict[str, int] = {}
        self._coaccess: Dict[str, Set[str]] = {}

        if state is not None:
            self.rebuild(state)

    def rebuild(self, state):
        """Rebuild index from current SystemState."""
        self._keyword_index.clear()
        self._tier_index.clear()
        self._memories.clear()
        self._access_count.clear()
        self._last_access.clear()
        self._coaccess.clear()

        # Index memories
        for mid, minfo in state.memory.items():
            self._memories[mid] = minfo
            tier = minfo.get('tier', 'episodic')
            self._tier_index[tier].add(mid)

            # Tokenize content for keyword search
            content = minfo.get('content', '')
            if content:
                for token in _tokenize(content):
                    self._keyword_index[token].add(mid)

            # Index tags if present
            for tag in minfo.get('tags', []):
                self._keyword_index[tag.lower()].add(mid)

        # Index access history for frequency and recency
        for entry in state.access_history:
            mid = entry.get('memory_id', '')
            tick = entry.get('tick', 0)
            self._access_count[mid] += 1
            if mid not in self._last_access or tick > self._last_access[mid]:
                self._last_access[mid] = tick

        # Copy co-access graph (sets -> sets)
        for mid, neighbors in state.coaccess_graph.items():
            self._coaccess[mid] = set(neighbors)

    def query(
        self,
        text: str,
        tier: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query memories by keyword text.

        Returns ranked list of dicts:
            {memory_id, content, tier, score, access_count, last_access_tick, coaccess}

        Scoring:
            - keyword match: +1.0 per matching token (normalized by query length)
            - tier bonus: +0.3 if tier matches filter
            - access frequency: +0.1 * log(1 + access_count)
            - recency: +0.2 * recency_factor (more recent = higher)
            - co-access boost: +0.1 * number of co-accessed memories
        """
        if not text:
            return self._recent_memories(tier, limit)

        query_tokens = _tokenize(text)
        if not query_tokens:
            return self._recent_memories(tier, limit)

        # Candidate: union of all keyword-matched memory IDs
        candidates: Set[str] = set()
        for token in query_tokens:
            candidates.update(self._keyword_index.get(token, set()))

        # Filter by tier
        if tier:
            tier_mems = self._tier_index.get(tier, set())
            candidates = candidates & tier_mems

        # Score each candidate
        current_tick = max(self._last_access.values()) if self._last_access else 0
        results = []
        for mid in candidates:
            minfo = self._memories[mid]

            # Keyword match score
            mem_tokens = _tokenize(minfo.get('content', ''))
            overlap = query_tokens & mem_tokens
            keyword_score = len(overlap) / len(query_tokens) if query_tokens else 0

            # Tier bonus
            tier_bonus = 0.3 if (tier and minfo.get('tier') == tier) else 0

            # Access frequency bonus
            import math
            freq_bonus = 0.1 * math.log(1 + self._access_count.get(mid, 0))

            # Recency bonus
            last_tick = self._last_access.get(mid, 0)
            if current_tick > 0:
                recency_bonus = 0.2 * (last_tick / current_tick)
            else:
                recency_bonus = 0

            # Co-access bonus
            coaccess_count = len(self._coaccess.get(mid, set()))
            coaccess_bonus = 0.1 * min(coaccess_count, 5)

            score = keyword_score + tier_bonus + freq_bonus + recency_bonus + coaccess_bonus

            if score >= min_score:
                results.append({
                    'memory_id': mid,
                    'content': minfo.get('content', ''),
                    'tier': minfo.get('tier', 'episodic'),
                    'score': round(score, 4),
                    'access_count': self._access_count.get(mid, 0),
                    'last_access_tick': self._last_access.get(mid, 0),
                    'coaccess': list(self._coaccess.get(mid, set()))[:5],
                })

        results.sort(key=lambda r: r['score'], reverse=True)
        return results[:limit]

    def _recent_memories(self, tier: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Return most recent memories (fallback when no query text)."""
        candidates = list(self._memories.items())
        if tier:
            candidates = [(mid, m) for mid, m in candidates if m.get('tier') == tier]

        candidates.sort(
            key=lambda x: self._last_access.get(x[0], 0),
            reverse=True,
        )
        return [
            {
                'memory_id': mid,
                'content': m.get('content', ''),
                'tier': m.get('tier', 'episodic'),
                'score': 0,
                'access_count': self._access_count.get(mid, 0),
                'last_access_tick': self._last_access.get(mid, 0),
                'coaccess': list(self._coaccess.get(mid, set()))[:5],
            }
            for mid, m in candidates[:limit]
        ]

    def get_related(self, memory_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get memories co-accessed with the given memory."""
        neighbors = self._coaccess.get(memory_id, set())
        results = []
        for mid in neighbors:
            if mid in self._memories:
                minfo = self._memories[mid]
                results.append({
                    'memory_id': mid,
                    'content': minfo.get('content', ''),
                    'tier': minfo.get('tier', 'episodic'),
                    'access_count': self._access_count.get(mid, 0),
                })
        results.sort(key=lambda r: r['access_count'], reverse=True)
        return results[:limit]

    def stats(self) -> Dict[str, Any]:
        """Index statistics."""
        return {
            'total_memories': len(self._memories),
            'tiers': {t: len(ids) for t, ids in self._tier_index.items()},
            'unique_tokens': len(self._keyword_index),
            'total_accesses': sum(self._access_count.values()),
            'coaccess_edges': sum(len(v) for v in self._coaccess.values()) // 2,
        }
