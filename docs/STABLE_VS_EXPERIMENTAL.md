# Stable vs Experimental Policy
=================================

## The Rule

```
stable/   ← Production, LKG, verified
experimental/ ← Research, unverified, NEVER production
archive/  ← Frozen history, never modified
```

## Why Separation Matters

1. **No accidental promotion** — experimental code cannot enter stable by accident
2. **Clean rollback** — archive always has a known-good state
3. **Evidence integrity** — benchmark results come only from stable
4. **Research stop condition** — when stable is "good enough", stop expanding

## Merge Criteria (stable ← experimental)

To promote from experimental/ to stable/:

```
□ Pass all bounded property checks
□ Pass full benchmark suite
□ No new unbounded dependencies
□ Observability data collected
□ Pathology catalog updated
□ Documentation updated
□ Policy approval (RUNTIME_POLICY.md Section 22)
□ Hash lock updated
□ Git tag created
```

## Emergency Rollback

If stable/ introduces regression:

```bash
# Immediate rollback
git checkout archive/v0.19f
cp -r archive/v0.19f/* stable/
# Restore stable tag
```

## What Never Goes to Stable

```
❌ experimental semantic governance ideas
❌ untested benchmark variations
❌ experimental retrieval physics
❌ unverified pathology fixes
❌ "temporary" patches
```
