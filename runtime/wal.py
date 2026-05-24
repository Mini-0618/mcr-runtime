"""
WAL (Write-Ahead Log) — Single Source of Truth
"""
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class Event:
    event_id: str
    event_type: str
    tick: int
    memory_id: Optional[str]
    coaccess_group_id: str
    payload: dict
    timestamp: float
    replay_hash: str

    def to_dict(self):
        d = asdict(self)
        d['_event_type'] = d.pop('event_type')
        return d

    @staticmethod
    def from_dict(d):
        d['event_type'] = d.pop('_event_type')
        return Event(**d)

    def _compute_replay_hash(self) -> str:
        """
        Compute integrity hash over the event, excluding replay_hash itself.
        This is computed at write time and validated at load time to detect
        post-write corruption (bit flip, truncation, replay attack, etc.).
        """
        d = self.to_dict()
        d.pop('replay_hash', None)
        # Serialize with sorted keys for deterministic output
        serialized = json.dumps(d, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _validate_replay_hash(self) -> bool:
        """
        Validate replay_hash against recomputed hash.
        Returns True if valid, False if missing or mismatched.
        An empty string means the field was never set (old WAL format);
        a mismatch means the event was modified after write.
        """
        if not self.replay_hash:
            return False
        return self.replay_hash == self._compute_replay_hash()

    def equals(self, other: 'Event') -> bool:
        """
        Compare two events for content equality, excluding replay_hash.
        replay_hash is computed at write time and may differ for
        otherwise-identical events written at different times. Excluding
        it lets callers compare event content across WAL loads.
        """
        return (
            self.event_id == other.event_id
            and self.event_type == other.event_type
            and self.tick == other.tick
            and self.memory_id == other.memory_id
            and self.coaccess_group_id == other.coaccess_group_id
            and self.payload == other.payload
            and abs(self.timestamp - other.timestamp) < 1e-6
        )


class WAL:
    def __init__(self, path: str = "/home/minimak/mcr/.wal/events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: List[Event] = []
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                for line in f:
                    if line.strip():
                        try:
                            d = json.loads(line)
                            event = Event.from_dict(d)
                            # Validate replay_hash integrity. Entries with empty replay_hash
                            # are old format (pre-migration); entries with mismatched hash
                            # indicate post-write corruption. Both are skipped so the system
                            # recovers via replay from the last valid prefix.
                            if not event._validate_replay_hash():
                                continue
                            self._events.append(event)
                        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                            # Malformed JSON or unexpected struct — skip this line.
                            # Covers corrupted, truncated, or manually edited WAL entries.
                            continue

    def append(self, event: Event):
        # Compute and store replay_hash before writing. This enables post-write
        # integrity validation on load: any tampering (bit flip, truncation,
        # manual edit) will cause _validate_replay_hash() to fail on load.
        event.replay_hash = event._compute_replay_hash()
        self._events.append(event)
        with open(self.path, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')
            f.flush()
        # Note: os.fsync() is needed for power-failure durability.
        # flush() ensures the event survives normal process exit (SIGTERM,
        # normal termination, OOM before final write).

    def get_all(self) -> List[Event]:
        return list(self._events)

    def clear(self):
        # Unlink file before clearing in-memory list.
        # If unlink fails (permissions, file not found), the in-memory list
        # is still intact and matches what reload would produce. Old order
        # (_events=[] first) would lose in-memory state if unlink() then fails.
        self.path.unlink(missing_ok=True)
        self._events = []

    def len(self) -> int:
        return len(self._events)

    def is_empty(self) -> bool:
        """True if WAL has no events. Useful for asserting clean slate."""
        return len(self._events) == 0
