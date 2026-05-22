"""
Memory System
Latent memory with relevance-based activation
"""
import json
import os
import uuid
from datetime import datetime
from typing import Any


class MemoryStore:
    """
    Memory is latent - not all in context.
    Only activated when relevant to current cognition.
    """
    
    def __init__(self, path: str):
        self.path = path
        self.memories: list[dict] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.memories = json.load(f).get("memories", [])

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"memories": self.memories}, f, ensure_ascii=False, indent=2)

    def store(
        self,
        content: str,
        memory_type: str = "general",
        importance: float = 0.5,
        tags: list[str] = None,
    ) -> str:
        """Store a new memory."""
        memory_id = str(uuid.uuid4())[:8]
        memory = {
            "id": memory_id,
            "content": content,
            "type": memory_type,
            "importance": importance,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "last_accessed": None,
            "access_count": 0,
            "activation_count": 0,
        }
        self.memories.append(memory)
        self.save()
        return memory_id

    def retrieve(
        self,
        query: str,
        max_results: int = 5,
        min_importance: float = 0.0,
    ) -> list[dict]:
        """
        Retrieve relevant memories based on query.
        Memory is latent - only returned when relevant.
        """
        if not query:
            return []

        # Simple keyword-based relevance scoring
        query_words = set(query.lower().split())
        scored = []

        for memory in self.memories:
            score = 0.0
            
            # Importance weight
            score += memory.get("importance", 0.5) * 0.3
            
            # Tag overlap
            memory_tags = set(memory.get("tags", []))
            tag_overlap = len(query_words & memory_tags)
            score += tag_overlap * 0.2
            
            # Content keyword match
            content_words = set(memory["content"].lower().split())
            content_overlap = len(query_words & content_words)
            score += content_overlap * 0.1
            
            # Recency bonus
            if memory.get("last_accessed"):
                days_old = (datetime.now() - datetime.fromisoformat(memory["last_accessed"])).days
                recency_bonus = max(0, 0.2 - days_old * 0.02)
                score += recency_bonus

            if score >= min_importance:
                memory["relevance_score"] = score
                memory["last_accessed"] = datetime.now().isoformat()
                memory["access_count"] += 1
                memory["activation_count"] += 1
                scored.append(memory)

        # Sort by score descending
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        result = scored[:max_results]
        
        # Update access stats
        self.save()
        
        return result

    def get_active_count(self) -> int:
        """Count memories that have been activated recently."""
        return len([m for m in self.memories if m.get("activation_count", 0) > 0])

    def prune_low_value(self, min_importance: float = 0.2) -> int:
        """Remove low-value memories to prevent memory bloat."""
        original_count = len(self.memories)
        self.memories = [
            m for m in self.memories
            if m.get("importance", 0) >= min_importance or m.get("access_count", 0) > 3
        ]
        self.save()
        return original_count - len(self.memories)

    def summarize(self) -> dict:
        """Get memory store statistics."""
        return {
            "total": len(self.memories),
            "by_type": self._count_by_type(),
            "by_importance": self._count_by_importance(),
            "total_activations": sum(m.get("activation_count", 0) for m in self.memories),
        }

    def _count_by_type(self) -> dict:
        counts = {}
        for m in self.memories:
            t = m.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def _count_by_importance(self) -> dict:
        return {
            "high": len([m for m in self.memories if m.get("importance", 0) >= 0.7]),
            "medium": len([m for m in self.memories if 0.4 <= m.get("importance", 0) < 0.7]),
            "low": len([m for m in self.memories if m.get("importance", 0) < 0.4]),
        }
