# Tombstone Lifecycle v1 — SPEC

## State Machine

```
working ──promote──→ episodic ──compact──→ semantic
    │                    │                      │
    │ LRU                │ LRU/decay            │ decay/pressure
    ↓                    ↓                      ↓
  [gone]              archive ──tomestone──→ tombstoned ──purge──→ [gone forever]
                         │                      │
                         │ hard_cap              │ purge_delay (deterministic)
                         ↓                      ↓
                       [gone]              purged (WAL-only record)
```

## Archive Item States

| State      | In Retrieve? | In Replay? | In CoAccess? | Persisted? |
|------------|--------------|------------|--------------|------------|
| archive    | ❌ (cold)    | ✅        | ✅           | ✅         |
| tombstoned | ❌           | ✅        | ❌ (inactive)| ✅         |
| purged     | ❌           | ❌        | ❌           | ❌ (metadata only in WAL) |

## Invariants

1. **tombstoned item不可被retrieve命中** — enforced in `access_memory()` lookup
2. **purged item不可在replay后复活** — WAL `archive_purge` event is terminal
3. **所有tombstone/purge事件必须进WAL** — via WALManager.append()
4. **event ordering稳定** — WAL seq + tick双重排序
5. **coaccess graph同步清理** — tombstoned memory's edges are marked inactive, purged memory's edges are removed

## WAL Events

```python
# archive_tombstone
WALManager.append(
    tick=current_tick,
    type="archive_tombstone",
    memory_id=memory["id"],
    from_state="archive",
    to_state="tombstoned",
    reason="decay_below_threshold | ttl_expired | archive_pressure",
)

# archive_purge
WALManager.append(
    tick=current_tick,
    type="archive_purge",
    memory_id=memory["id"],
    from_state="tombstoned",
    to_state="purged",
    reason="purge_delay_expired",
)
```

## Tombstone Conditions (v1 — deterministic)

```python
# Condition: archive memory has been tombstoned at least PURGE_DELAY ticks
# No complex scoring — just time-based deterministic
PURGE_DELAY = 100  # ticks

def should_tombstone(memory, current_tick) -> bool:
    return memory["state"] == "archive"

def should_purge(memory, current_tick) -> bool:
    if memory["state"] != "tombstoned":
        return False
    age = current_tick - memory["tombstoned_at"]
    return age >= PURGE_DELAY
```

## Retrieval Filter

```python
# In access_memory() and retrieve():
# Skip any memory where state in ("tombstoned", "purged")
```

## CoAccess Graph Sync

```python
# When memory is tombstoned:
coaccess.mark_inactive(memory_id)

# When memory is purged:
coaccess.remove_memory(memory_id)
```

## Replay Contract

After full WAL replay:
- archive layer = memories that were NOT tombstoned or purged
- tombstoned set = memories in `tombstoned` state (replay-state reconstruction)
- purged set = memory_ids in `archive_purge` WAL events (never resurrected)
