"""
wal.py — MCR Write-Ahead Log

Append-only event log. Single source of truth for MCR's event-sourced state.

Each line in the WAL is a JSON event with:
  - _event_type field (event type for type-based recovery)
  - replay_hash for post-write integrity validation

The WAL is the only authoritative record. Runtime state is derived from WAL
via replay. This means the system can always recover from WAL after a crash.

Key invariants:
  1. WAL is append-only. Nothing is ever edited or deleted mid-WAL.
  2. Each event carries a replay_hash computed at write time.
  3. On load, replay_hash is validated. Invalid entries are skipped.
  4. replay(WAL from empty) == runtime_state (G2 invariant)
"""
from pathlib import Path
from typing import List

from .events import MCREvent

# Backward-compat: old code imports Event from wal.py
Event = MCREvent


class WAL:
    """
    Append-only WAL with replay_hash integrity validation.

    Write path:
      1. Compute replay_hash for the event
      2. Append JSON line to file
      3. flush() to survive normal process exit

    Load path:
      1. Read lines
      2. Parse JSON
      3. Validate replay_hash
      4. Skip bad entries (corrupted, tampered, truncated)

    Note: fsync() is NOT called. Power-failure during the final flush() may
    lose the last event. This is a documented durability tradeoff for v0.x.
    For power-safe writes, add os.fsync() after flush() in append().
    """

    def __init__(self, path: str = "./.wal/events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: List[MCREvent] = []
        self._load()

    def _load(self) -> None:
        """Load and validate WAL from disk. Skip corrupted/tampered entries."""
        if not self.path.exists():
            return

        with self.path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = __import__('json').loads(line)
                    event = MCREvent.from_dict(d)
                    # Validate replay_hash integrity. Entries with empty or
                    # mismatched hash indicate post-write corruption.
                    # Skip so replay recovers from last valid prefix.
                    if not event.validate_replay_hash():
                        continue
                    self._events.append(event)
                except (KeyError, ValueError, TypeError):
                    # Malformed JSON or unexpected struct — skip.
                    continue

    def append(self, event: MCREvent) -> None:
        """
        Append event to WAL. Computes replay_hash before writing so load-time
        can detect post-write corruption.
        """
        event = MCREvent(
            event_id=event.event_id,
            event_type=event.event_type,
            tick=event.tick,
            memory_id=event.memory_id,
            coaccess_group_id=event.coaccess_group_id,
            payload=event.payload,
            timestamp=event.timestamp,
            # Compute hash AFTER constructing full event (excludes hash itself)
            replay_hash=event.compute_replay_hash(),
        )
        with self.path.open('a') as f:
            f.write(__import__('json').dumps(event.to_dict()) + '\n')
            f.flush()
        self._events.append(event)

    def get_all(self) -> List[MCREvent]:
        """Return a snapshot of all events."""
        return list(self._events)

    def clear(self) -> None:
        """Delete WAL file and reset in-memory event list."""
        self.path.unlink(missing_ok=True)
        self._events = []

    def len(self) -> int:
        return len(self._events)

    def is_empty(self) -> bool:
        """True if WAL has no events."""
        return len(self._events) == 0