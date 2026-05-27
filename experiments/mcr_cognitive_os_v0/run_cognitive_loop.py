"""
run_cognitive_loop.py — MCR Cognitive OS v0.1 Orchestrator

Runs a single cognitive cycle:
  Perception → Attention → Scoring → Policy → Planning → Action → Reflection → Memory → Verification

All local. No network. No secrets. No runtime modification.
"""
import json
import sys
import time
import uuid
from pathlib import Path

# Ensure project root is importable
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_experiment_dir = Path(__file__).resolve().parent
if str(_experiment_dir) not in sys.path:
    sys.path.insert(0, str(_experiment_dir))

from state_reader import StateReader
from attention_filter import AttentionFilter
from task_scorer import TaskScorer
from goal_manager import GoalManager
from policy_engine import PolicyEngine, PolicyVerdict
from planner import Planner
from action_selector import ActionSelector
from reflection_engine import ReflectionEngine
from memory_writer import MemoryWriter


def run_cognitive_loop() -> dict:
    """Execute one full cognitive cycle. Returns result dict."""
    cycle_id = str(uuid.uuid4())[:8]
    tasks_path = str(_experiment_dir / "tasks.json")
    wal_path = str(_experiment_dir / "logs" / "cognitive_wal.jsonl")
    latest_run_path = str(_experiment_dir / "logs" / "latest_run.json")

    # ── Perception ──
    reader = StateReader(tasks_path)
    perception = reader.perceive()

    # ── Attention ──
    attn = AttentionFilter(urgency_threshold=0.3)
    attended = attn.filter(perception["tasks"])

    # ── Scoring ──
    scorer = TaskScorer()
    scored = scorer.score(attended)
    ranked = scorer.rank(scored)

    # ── Goal ──
    goal_mgr = GoalManager()
    goal_mgr.set_goal("stability", reason="Runtime is in freeze/bugfix-only phase")

    # ── Policy ──
    policy = PolicyEngine()
    allowed_tasks = []
    blocked_tasks = []
    owner_tasks = []
    for task in ranked:
        verdict = policy.check(task)
        if verdict.status == PolicyVerdict.ALLOWED:
            allowed_tasks.append(task)
        elif verdict.status == PolicyVerdict.REQUIRES_OWNER:
            owner_tasks.append({"task": task, "verdict": verdict.to_dict()})
        else:
            blocked_tasks.append({"task": task, "verdict": verdict.to_dict()})

    # ── Planning ──
    planner = Planner()
    plan = planner.plan(allowed_tasks, max_actions=3)

    # ── Action Selection ──
    selector = ActionSelector()
    next_action = selector.select_next(plan)

    # ── Reflection ──
    reflector = ReflectionEngine()
    policy_status = "allowed" if next_action else "no_action"
    reflection = reflector.reflect(
        action=next_action or {},
        policy_verdict=policy_status,
        task_count=perception["task_count"],
        attended_count=len(attended),
    )

    # ── Memory (via MCR runtime) ──
    mem = MemoryWriter(wal_path=wal_path)
    mem.store_action(next_action or {"title": "no_action"}, cycle_id)
    mem.store_reflection(reflection, cycle_id)

    # ── Verification ──
    verify_result = mem.verify_replay()

    # ── Build result ──
    result = {
        "cycle_id": cycle_id,
        "perception": {
            "task_count": perception["task_count"],
            "pending_count": perception["pending_count"],
        },
        "attention": {
            "attended_count": len(attended),
            "filtered_count": perception["task_count"] - len(attended),
        },
        "scoring": {
            "top_task": ranked[0]["title"] if ranked else "none",
            "top_score": ranked[0]["score"] if ranked else 0,
        },
        "goal": goal_mgr.describe(),
        "policy": {
            "allowed": len(allowed_tasks),
            "blocked": len(blocked_tasks),
            "requires_owner": len(owner_tasks),
            "blocked_details": blocked_tasks,
            "owner_details": owner_tasks,
        },
        "plan": plan,
        "next_action": next_action,
        "reflection": reflection,
        "replay_verification": {
            "match": verify_result["match"],
            "reason": verify_result["reason"],
            "runtime_hash": verify_result.get("runtime_hash"),
            "replay_hash": verify_result.get("replay_hash"),
            "wal_length": verify_result.get("wal_length"),
        },
    }

    # ── Write latest_run.json ──
    Path(latest_run_path).parent.mkdir(parents=True, exist_ok=True)
    with open(latest_run_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result


def main():
    """Run the cognitive loop and print results."""
    print("=" * 60)
    print("MCR COGNITIVE OS v0.1")
    print("=" * 60)

    result = run_cognitive_loop()

    # Print summary
    print(f"\nCycle ID: {result['cycle_id']}")
    print(f"Tasks: {result['perception']['task_count']} total, "
          f"{result['perception']['pending_count']} pending")
    print(f"Attention: {result['attention']['attended_count']} passed, "
          f"{result['attention']['filtered_count']} filtered")
    print(f"Top task: {result['scoring']['top_task']} "
          f"(score={result['scoring']['top_score']})")
    print(f"Goal: {result['goal']['current_goal']}")
    print(f"Policy: {result['policy']['allowed']} allowed, "
          f"{result['policy']['blocked']} blocked, "
          f"{result['policy']['requires_owner']} need owner")

    if result["policy"]["blocked_details"]:
        print("\n  Blocked:")
        for b in result["policy"]["blocked_details"]:
            print(f"    - {b['task']['title']}: {b['verdict']['reason']}")

    if result["policy"]["owner_details"]:
        print("\n  Requires Owner:")
        for o in result["policy"]["owner_details"]:
            print(f"    - {o['task']['title']}: {o['verdict']['reason']}")

    print(f"\nPlan:")
    for i, a in enumerate(result["plan"], 1):
        print(f"  {i}. {a['title']} ({a['action_type']}, score={a['score']})")

    na = result["next_action"]
    if na:
        print(f"\nNext Action: {na['title']}")
    else:
        print(f"\nNext Action: none")

    ref = result["reflection"]
    print(f"\nReflection: {ref['lesson']}")
    print(f"  Good choice: {ref['was_good_choice']}")

    rv = result["replay_verification"]
    print(f"\nReplay Verification: {'PASS' if rv['match'] else 'FAIL'}")
    print(f"  Reason: {rv['reason']}")
    print(f"  Runtime hash: {rv['runtime_hash'][:16]}...")
    print(f"  WAL length: {rv['wal_length']}")

    # Final verdict
    all_pass = rv["match"]
    print("\n" + "=" * 60)
    if all_pass:
        print("MCR COGNITIVE OS v0.1 PASS")
    else:
        print("MCR COGNITIVE OS v0.1 FAIL")
    print("=" * 60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
