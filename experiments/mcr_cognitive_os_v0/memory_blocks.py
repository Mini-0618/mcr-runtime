"""
memory_blocks.py — MCR Cognitive OS v0.2 Memory Block System

Three memory block types:
  persona   — Owner style, boundaries, long-term direction (read-only)
  context   — Current project state (updated each cycle)
  knowledge — Lessons learned from task outcomes (accumulates)
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PERSONA = {
    "name": "MCR Cognitive OS",
    "role": "认知判断层",
    "boundaries": [
        "不自行决定高风险操作",
        "不绕过 Owner 批准",
        "不修改 Runtime 核心",
        "不联网执行未知代码",
        "不真实控制浏览器",
        "不真实发送社交媒体消息",
    ],
    "values": [
        "安全优先",
        "可验证性",
        "最小惊讶原则",
    ],
}


class MemoryBlocks:
    """Manages three memory block types for the cognitive loop."""

    def __init__(self):
        self.persona: Dict[str, Any] = dict(DEFAULT_PERSONA)
        self.context: Dict[str, Any] = {}
        self.knowledge: List[Dict[str, Any]] = []

    def set_persona(self, persona: Dict[str, Any]):
        """Set persona block (Owner-configured, read-only during cycle)."""
        self.persona = persona

    def update_context(self, key: str, value: Any):
        """Update a context field (overwritten each cycle)."""
        self.context[key] = value

    def clear_context(self):
        """Clear context block for fresh cycle."""
        self.context = {}

    def add_knowledge(self, lesson: str, source: str = "", confidence: float = 0.5):
        """Add a knowledge entry from task outcome."""
        self.knowledge.append({
            "lesson": lesson,
            "source": source,
            "confidence": confidence,
        })

    def check_persona_boundary(self, action: str) -> bool:
        """Check if an action violates persona boundaries."""
        action_lower = action.lower()
        for boundary in self.persona.get("boundaries", []):
            boundary_lower = boundary.lower()
            # Check if action matches boundary keywords
            keywords = [w for w in boundary_lower.split() if len(w) > 2]
            if any(kw in action_lower for kw in keywords):
                return False  # boundary violated
        return True  # action is within persona

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all blocks for latest_run.json."""
        return {
            "persona": self.persona,
            "context": self.context,
            "knowledge": self.knowledge,
        }

    def save(self, path: str):
        """Save blocks to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: str) -> "MemoryBlocks":
        """Load blocks from JSON file."""
        blocks = MemoryBlocks()
        if not Path(path).exists():
            return blocks
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        blocks.persona = data.get("persona", DEFAULT_PERSONA)
        blocks.context = data.get("context", {})
        blocks.knowledge = data.get("knowledge", [])
        return blocks
