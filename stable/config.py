"""
MCR Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "world_state.json")
EVENT_FILE = os.path.join(BASE_DIR, "event_queue.json")
TRACE_DIR = os.path.join(BASE_DIR, "cognition_trace")
SNAPSHOT_DIR = os.path.join(BASE_DIR, "state_snapshots")

# Cognitive loop interval (seconds)
TICK_INTERVAL = 60

# Snapshot every N ticks
SNAPSHOT_EVERY = 10

# Max events to process per tick
MAX_EVENTS_PER_TICK = 20

# Memory activation limit
MAX_ACTIVE_MEMORIES = 5

# Drift thresholds
DRIFT_THRESHOLDS = {
    "goal": 0.3,
    "reasoning": 0.4,
    "context_pollution": 0.5,
    "execution": 0.3,
}

# State compression triggers
COMPRESSION_TRIGGERS = {
    "event_queue_size": 50,
    "context_length": 8000,
    "memory_size": 100,
}

# Memory review interval (ticks between full periodic reviews; 0 = disabled)
REVIEW_INTERVAL = 50

# Semantic retrieval budget
SEMANTIC_RETRIEVAL_K = 2
