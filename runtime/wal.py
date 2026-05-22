"""
WAL (Write-Ahead Log) — Single Source of Truth
"""
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
                        d = json.loads(line)
                        self._events.append(Event.from_dict(d))

    def append(self, event: Event):
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
        self._events = []
        if self.path.exists():
            self.path.unlink()

    def len(self) -> int:
        return len(self._events)
