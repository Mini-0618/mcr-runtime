#!/bin/bash
cd /home/minimak/mcr

END=$((SECONDS+18000))

echo "===== MCR 5H SUPERVISED LOOP START $(date) =====" >> runtime_loop.log

while [ $SECONDS -lt $END ]; do
  echo "" >> runtime_loop.log
  echo "===== CYCLE START $(date) =====" >> runtime_loop.log

  tmux send-keys -t mcr5h "Read ARCHITECTURE_LOCK.md first.

Environment constraints:
- pytest is NOT installed.
- Run tests only with:
  python3 tests/test_g2_replay.py
  python3 tests/test_event_gate.py
- Do not add dependencies.

Mission:
Run exactly one small MCR runtime engineering cycle.

Hard invariants:
- Hermes is proposal-only.
- All state transitions must flow through EventGate -> Reducer -> WAL -> State -> ReplayVerifier.
- Never mutate state directly.
- Never bypass reducer.
- Preserve replay determinism.
- Preserve WAL correctness.
- Preserve event ordering.
- Preserve crash recovery.
- Old WAL must remain replayable.
- Reducer must remain pure.
- Engine owns tick authority.
- LLM must not assign ticks.
- No hidden mutable runtime state outside replayable/snapshotable state.
- Do not weaken tests.

Allowed targets:
1. ARCHITECTURE_LOCK hardening
2. explicit test runner documentation
3. replay verifier hardening
4. EventGate validation edge case
5. HermesBridge prompt/environment constraint handling
6. runtime supervisor design note
7. behavioral replay verification
8. deterministic iteration/seed lockdown
9. capability benchmark note

Execution:
1. inspect code and tests
2. choose exactly one smallest useful mechanism
3. implement only that mechanism if safe
4. run:
   python3 tests/test_g2_replay.py
   python3 tests/test_event_gate.py
5. if tests pass, commit with concise message
6. if tests fail, fix your own change or revert your own change
7. report concise result

Forbidden:
- broad refactor
- architecture rewrite
- reducer bypass
- direct state mutation
- changing WAL format unless versioned
- adding dependencies
- UI work
- speculative AGI/L7 claims
- committing failing tests
- cosmetic-only commit
" C-m

  sleep 270

  echo "===== DRIVER TESTS $(date) =====" >> runtime_loop.log
  python3 tests/test_g2_replay.py >> runtime_loop.log 2>&1
  python3 tests/test_event_gate.py >> runtime_loop.log 2>&1

  echo "===== DRIVER GIT STATUS $(date) =====" >> runtime_loop.log
  git status --short >> runtime_loop.log 2>&1

  echo "===== DRIVER RECENT COMMITS =====" >> runtime_loop.log
  git log --oneline -5 >> runtime_loop.log 2>&1

  echo "===== CYCLE END $(date) =====" >> runtime_loop.log

  sleep 30
done

echo "===== MCR 5H SUPERVISED LOOP COMPLETE $(date) =====" >> runtime_loop.log
