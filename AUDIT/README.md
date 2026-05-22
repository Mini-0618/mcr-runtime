# MCR Audit Layer v1.0
======================

**Purpose:** Immutable change record for all system modifications.
**Owner:** SYSTEM Terminal

## Audit Entry Schema
entry_id | timestamp | terminal | action_type | scope | hash

## Rules
1. Append-only - Never modify/delete audit logs
2. SYSTEM only writes
3. Every handoff logged
4. Snapshot references for every MODIFY
5. Rollback chain for every rollback

*v1.0 FROZEN
