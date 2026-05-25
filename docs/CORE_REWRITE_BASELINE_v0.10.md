# MCR Core Rewrite Baseline v0.10

**Date:** 2026-05-25
**Branch:** rewrite/core-v2-candidate
**From:** 1b7156f Add minimal agent orchestrator

---

## Pre-Rewrite Baseline

### verify_all.sh


### pytest


### build_check.sh


### Current Architecture


### Invariant


### Key Design Properties
- Append-only WAL with replay_hash validation
- Clone-before-mutate state model
- Deterministic SHA-256 state hash with fixed salt
- Pure reducer handlers
- EventGate enforced tick authority (Engine owns ticks)
- No external API dependencies

---

## What Works Well
- G2 invariant is solid
- Clone model prevents mutation leaks
- Deterministic hash is stable across sessions
- EventGate rules are comprehensive
- No pytest dependency for tests

## What Needs Improvement
- README badge shows v0.9.3 instead of v0.9.7
- Package namespace is `runtime` (conflicts with stdlib potential)
- No dedicated `events.py` — Event model is embedded in wal.py
- G2 verification tick_interval hardcoded to 10
- MAX_SNAPSHOT_ACCESS_HISTORY hardcoded to 20

## Environment
- Python 3.12.3 on WSL Ubuntu
- Git SSH remote (no auth for push)
- Working directory: /home/minimak/mcr
