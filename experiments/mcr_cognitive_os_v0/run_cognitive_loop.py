"""
run_cognitive_loop.py — MCR Cognitive OS v0.1 Orchestrator

Runs a single cognitive cycle:
  Perception → Attention → Scoring → Policy → Planning → Action → Reflection → Memory → Verification

Supports three input modes:
  1. Default: reads tasks.json
  2. --task "description": single task from CLI
  3. --stdin: read task(s) from stdin (one per line)

All local. No network. No secrets. No runtime modification.
"""
import argparse
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
from input_adapter import text_to_task, text_to_tasks, format_task_report


def get_tasks(mode: str, task_text: str = None) -> list:
    """Load tasks based on input mode."""
    tasks_path = str(_experiment_dir / "tasks.json")

    if mode == "task" and task_text:
        return [text_to_task(task_text)]
    elif mode == "stdin":
        raw = sys.stdin.read().strip()
        if not raw:
            print("ERROR: No input received from stdin", file=sys.stderr)
            sys.exit(1)
        # Multi-line: one task per line
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        if len(lines) == 1:
            return [text_to_task(lines[0])]
        return text_to_tasks(raw)
    else:
        # Default: read tasks.json
        reader = StateReader(tasks_path)
        perception = reader.perceive()
        return perception["tasks"]


def run_cognitive_loop(mode: str = "default", task_text: str = None) -> dict:
    """Execute one full cognitive cycle. Returns result dict."""
    cycle_id = str(uuid.uuid4())[:8]
    wal_path = str(_experiment_dir / "logs" / "cognitive_wal.jsonl")
    latest_run_path = str(_experiment_dir / "logs" / "latest_run.json")

    # Clean WAL for fresh run
    Path(wal_path).unlink(missing_ok=True)

    # ── Perception ──
    tasks = get_tasks(mode, task_text)
    task_count = len(tasks)
    pending_count = sum(1 for t in tasks if t.get("status") == "pending")

    # ── Attention ──
    attn = AttentionFilter(urgency_threshold=0.3)
    attended = attn.filter(tasks)

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

    # If no action selected but there are owner-required tasks, signal ASK_OWNER
    ask_owner = False
    if not next_action and owner_tasks:
        ask_owner = True
        next_action = {
            "task_id": "ASK_OWNER",
            "title": "ASK_OWNER: " + owner_tasks[0]["task"].get("title", ""),
            "action_type": "escalate",
            "score": 0,
            "estimated_cost": 0,
        }

    # ── Reflection ──
    reflector = ReflectionEngine()
    if ask_owner:
        policy_status = "requires_owner"
    elif next_action:
        policy_status = "allowed"
    else:
        policy_status = "no_action"
    reflection = reflector.reflect(
        action=next_action or {},
        policy_verdict=policy_status,
        task_count=task_count,
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
        "input_mode": mode,
        "perception": {
            "task_count": task_count,
            "pending_count": pending_count,
        },
        "attention": {
            "attended_count": len(attended),
            "filtered_count": task_count - len(attended),
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
        "ask_owner": ask_owner,
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


def print_result(result: dict):
    """Print formatted result to stdout."""
    print("=" * 60)
    print("MCR COGNITIVE OS v0.1")
    print("=" * 60)

    print(f"\nCycle ID: {result['cycle_id']}")
    print(f"Input Mode: {result['input_mode']}")
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
    if result["plan"]:
        for i, a in enumerate(result["plan"], 1):
            print(f"  {i}. {a['title']} ({a['action_type']}, score={a['score']})")
    else:
        print("  (no actionable tasks)")

    na = result["next_action"]
    if na:
        label = na["title"]
        if result.get("ask_owner"):
            print(f"\n>>> DECISION: {label}")
            print(f"    This task requires your approval before proceeding.")
        else:
            print(f"\nNext Action: {label}")
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

    all_pass = rv["match"]
    print("\n" + "=" * 60)
    if all_pass:
        print("MCR COGNITIVE OS v0.1 PASS")
    else:
        print("MCR COGNITIVE OS v0.1 FAIL")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="MCR Cognitive OS v0.1 — Cognitive decision loop"
    )
    parser.add_argument(
        "--task", type=str, default=None,
        help="Single task description (CLI mode)"
    )
    parser.add_argument(
        "--stdin", action="store_true", default=False,
        help="Read task(s) from stdin, one per line"
    )
    args = parser.parse_args()

    if args.task:
        mode = "task"
        task_text = args.task
    elif args.stdin:
        mode = "stdin"
        task_text = None
    else:
        mode = "default"
        task_text = None

    result = run_cognitive_loop(mode=mode, task_text=task_text)
    print_result(result)

    return 0 if result["replay_verification"]["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
