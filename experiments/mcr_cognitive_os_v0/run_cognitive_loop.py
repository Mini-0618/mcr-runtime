"""
run_cognitive_loop.py — MCR Cognitive OS v0.2 Orchestrator

State-machine-driven cognitive cycle:
  INTAKE → READ_STATE → ATTENTION → SCORE → POLICY → PLAN → SELECT_ACTION → REFLECT → MEMORY_WRITE → VERIFY → DONE

Supports: ASK_OWNER (pause for approval), STOP (block high risk)
Input modes: default (tasks.json), --task, --stdin
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

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
from input_adapter import text_to_task, text_to_tasks
from state_machine import StateMachine
from memory_blocks import MemoryBlocks
from browser_operator import MockBrowserOperator
from memory_evolution import MemoryEvolution


def get_tasks(mode: str, task_text: str = None) -> list:
    tasks_path = str(_experiment_dir / "tasks.json")
    if mode == "task" and task_text:
        return [text_to_task(task_text)]
    elif mode == "stdin":
        raw = sys.stdin.read().strip()
        if not raw:
            print("ERROR: No input from stdin", file=sys.stderr)
            sys.exit(1)
        # Sanitize: replace surrogates that Windows stdin may produce
        raw = raw.encode("utf-8", errors="replace").decode("utf-8")
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        return [text_to_task(lines[0])] if len(lines) == 1 else text_to_tasks(raw)
    else:
        reader = StateReader(tasks_path)
        return reader.perceive()["tasks"]


def run_cognitive_loop(mode: str = "default", task_text: str = None) -> dict:
    cycle_id = str(uuid.uuid4())[:8]
    wal_path = str(_experiment_dir / "logs" / "cognitive_wal.jsonl")
    latest_run_path = str(_experiment_dir / "logs" / "latest_run.json")
    blocks_path = str(_experiment_dir / "logs" / "memory_blocks.json")

    Path(wal_path).unlink(missing_ok=True)

    sm = StateMachine()
    blocks = MemoryBlocks()
    browser = MockBrowserOperator()
    mem = MemoryWriter(wal_path=wal_path)

    # ── INTAKE ──
    tasks = get_tasks(mode, task_text)
    sm.transition("READ_STATE", f"Loaded {len(tasks)} tasks")

    # ── READ_STATE ──
    task_count = len(tasks)
    pending_count = sum(1 for t in tasks if t.get("status") == "pending")
    blocks.update_context("task_count", task_count)
    blocks.update_context("pending_count", pending_count)
    blocks.update_context("input_mode", mode)
    sm.transition("ATTENTION", f"State read: {pending_count} pending")

    # ── ATTENTION ──
    attn = AttentionFilter(urgency_threshold=0.3)
    attended = attn.filter(tasks)
    sm.transition("SCORE", f"{len(attended)} tasks passed attention")

    # ── SCORE ──
    scorer = TaskScorer()
    scored = scorer.score(attended)
    ranked = scorer.rank(scored)
    top_title = ranked[0]["title"] if ranked else "none"
    top_score = ranked[0]["score"] if ranked else 0
    sm.transition("POLICY", f"Top: {top_title} ({top_score})")

    # ── POLICY ──
    policy = PolicyEngine()
    allowed_tasks, blocked_tasks, owner_tasks = [], [], []
    for task in ranked:
        verdict = policy.check(task)
        if verdict.status == PolicyVerdict.ALLOWED:
            allowed_tasks.append(task)
        elif verdict.status == PolicyVerdict.REQUIRES_OWNER:
            owner_tasks.append({"task": task, "verdict": verdict.to_dict()})
        else:
            blocked_tasks.append({"task": task, "verdict": verdict.to_dict()})

    # High risk → STOP
    if blocked_tasks and not allowed_tasks and not owner_tasks:
        sm.transition("STOP", f"All tasks blocked: {blocked_tasks[0]['verdict']['reason']}")
        result = _build_result(cycle_id, mode, sm, blocks, browser, mem,
                               task_count, pending_count, attended, ranked,
                               allowed_tasks, blocked_tasks, owner_tasks,
                               plan=[], next_action=None, ask_owner=False,
                               verify_result={"match": True, "reason": "ok", "runtime_hash": "", "wal_length": 0},
                               memory_evolution=None)
        _write_output(latest_run_path, blocks_path, blocks, result)
        return result

    # Requires owner → ASK_OWNER
    if owner_tasks and not allowed_tasks:
        sm.transition("ASK_OWNER", f"Needs approval: {owner_tasks[0]['task']['title']}")
        ask_owner = True
        next_action = {
            "task_id": "ASK_OWNER",
            "title": "ASK_OWNER: " + owner_tasks[0]["task"].get("title", ""),
            "action_type": "escalate", "score": 0, "estimated_cost": 0,
        }
        plan = []
        sm.transition("STOP", "Waiting for owner decision")
        result = _build_result(cycle_id, mode, sm, blocks, browser, mem,
                               task_count, pending_count, attended, ranked,
                               allowed_tasks, blocked_tasks, owner_tasks,
                               plan, next_action, ask_owner,
                               verify_result={"match": True, "reason": "ok", "runtime_hash": "", "wal_length": 0},
                               memory_evolution=None)
        _write_output(latest_run_path, blocks_path, blocks, result)
        return result

    sm.transition("PLAN", f"{len(allowed_tasks)} tasks allowed")

    # ── PLAN ──
    goal_mgr = GoalManager()
    goal_mgr.set_goal("stability", reason="Runtime freeze/bugfix-only")
    planner = Planner()
    plan = planner.plan(allowed_tasks, max_actions=3)
    sm.transition("SELECT_ACTION", f"Plan: {len(plan)} actions")

    # ── SELECT_ACTION ──
    selector = ActionSelector()
    next_action = selector.select_next(plan)
    ask_owner = False

    # Browser observation (mock)
    browser_observation = None
    if next_action:
        page = browser.observe()
        proposed = browser.propose_actions(next_action.get("title", ""))
        browser_observation = {
            "page": page.to_dict(),
            "proposed_actions": proposed,
        }

    sm.transition("REFLECT", f"Selected: {next_action['title'] if next_action else 'none'}")

    # ── REFLECT ──
    reflector = ReflectionEngine()
    reflection = reflector.reflect(
        action=next_action or {},
        policy_verdict="allowed",
        task_count=task_count,
        attended_count=len(attended),
    )
    # Add lesson to knowledge block
    blocks.add_knowledge(reflection["lesson"], source=cycle_id, confidence=0.7)

    # ── MEMORY EVOLUTION ──
    evolution_path = str(_experiment_dir / "logs" / "latest_run.json")
    evolver = MemoryEvolution(history_path=evolution_path if Path(evolution_path).exists() else None)
    # Build partial result for evolution analysis
    partial_result = {
        "reflection": reflection,
        "policy": {"allowed": len(allowed_tasks), "blocked": len(blocked_tasks), "requires_owner": len(owner_tasks)},
        "execution": None,
        "final_state": sm.current(),
        "scoring": {"top_task": ranked[0]["title"] if ranked else "none", "top_score": ranked[0]["score"] if ranked else 0},
        "attention": {"attended_count": len(attended), "filtered_count": task_count - len(attended)},
    }
    evolution_record = evolver.evolve(partial_result)
    blocks.add_knowledge(f"Evolution: {evolution_record.reuse_next_time or evolution_record.avoid_next_time or 'no pattern'}",
                         source=cycle_id, confidence=evolution_record.confidence)

    sm.transition("MEMORY_WRITE", f"Reflection: {reflection['was_good_choice']}")

    # ── MEMORY_WRITE ──
    mem.store_action(next_action or {"title": "no_action"}, cycle_id)
    mem.store_reflection(reflection, cycle_id)
    sm.transition("VERIFY", "Events written to WAL")

    # ── VERIFY ──
    verify_result = mem.verify_replay()
    sm.transition("DONE", f"Replay: {'PASS' if verify_result['match'] else 'FAIL'}")

    result = _build_result(cycle_id, mode, sm, blocks, browser, mem,
                           task_count, pending_count, attended, ranked,
                           allowed_tasks, blocked_tasks, owner_tasks,
                           plan, next_action, ask_owner,
                           verify_result, browser_observation, memory_evolution=evolution_record)
    _write_output(latest_run_path, blocks_path, blocks, result)
    return result


def _build_result(cycle_id, mode, sm, blocks, browser, mem,
                  task_count, pending_count, attended, ranked,
                  allowed_tasks, blocked_tasks, owner_tasks,
                  plan, next_action, ask_owner,
                  verify_result, browser_observation=None, memory_evolution=None):
    return {
        "cycle_id": cycle_id,
        "version": "v0.2",
        "input_mode": mode,
        "state_trace": sm.get_trace(),
        "final_state": sm.current(),
        "perception": {"task_count": task_count, "pending_count": pending_count},
        "attention": {
            "attended_count": len(attended),
            "filtered_count": task_count - len(attended),
        },
        "scoring": {
            "top_task": ranked[0]["title"] if ranked else "none",
            "top_score": ranked[0]["score"] if ranked else 0,
        },
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
        "reflection": {
            "lesson": blocks.knowledge[-1]["lesson"] if blocks.knowledge else "",
            "was_good_choice": True,
        },
        "memory_blocks": blocks.to_dict(),
        "browser_observation": browser_observation,
        "memory_evolution": memory_evolution.to_dict() if memory_evolution else None,
        "replay_verification": {
            "match": verify_result.get("match", True),
            "reason": verify_result.get("reason", "ok"),
            "runtime_hash": verify_result.get("runtime_hash", ""),
            "wal_length": verify_result.get("wal_length", 0),
        },
    }


def _write_output(latest_run_path, blocks_path, blocks, result):
    Path(latest_run_path).parent.mkdir(parents=True, exist_ok=True)
    with open(latest_run_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    blocks.save(blocks_path)


def print_result(result: dict):
    print("=" * 60)
    print("MCR COGNITIVE OS v0.2")
    print("=" * 60)

    print(f"\nCycle: {result['cycle_id']} | Mode: {result['input_mode']}")
    print(f"Final State: {result['final_state']}")

    print(f"\nState Trace:")
    for step in result["state_trace"]:
        print(f"  {step['state']:20s} ← {step['reason']}")

    print(f"\nTasks: {result['perception']['task_count']} total, "
          f"{result['perception']['pending_count']} pending")
    print(f"Attention: {result['attention']['attended_count']} passed, "
          f"{result['attention']['filtered_count']} filtered")
    print(f"Top: {result['scoring']['top_task']} (score={result['scoring']['top_score']})")

    p = result["policy"]
    print(f"Policy: {p['allowed']} allowed, {p['blocked']} blocked, {p['requires_owner']} need owner")

    if p["blocked_details"]:
        for b in p["blocked_details"]:
            print(f"  BLOCKED: {b['task']['title']} — {b['verdict']['reason']}")
    if p["owner_details"]:
        for o in p["owner_details"]:
            print(f"  ASK_OWNER: {o['task']['title']} — {o['verdict']['reason']}")

    print(f"\nPlan:")
    for i, a in enumerate(result["plan"], 1):
        print(f"  {i}. {a['title']} ({a['action_type']}, score={a['score']})")

    na = result["next_action"]
    if na:
        label = na["title"]
        if result.get("ask_owner"):
            print(f"\n>>> DECISION: {label}")
        else:
            print(f"\nNext Action: {label}")
    else:
        print(f"\nNext Action: none")

    print(f"\nReflection: {result['reflection']['lesson']}")

    mb = result.get("memory_blocks", {})
    if mb:
        print(f"\nMemory Blocks:")
        print(f"  Persona: {mb['persona'].get('name', '?')} — {mb['persona'].get('role', '?')}")
        print(f"  Context: {len(mb.get('context', {}))} fields")
        print(f"  Knowledge: {len(mb.get('knowledge', []))} entries")

    bo = result.get("browser_observation")
    if bo:
        print(f"\nBrowser (mock): {bo['page']['title']}")
        print(f"  Proposed actions: {len(bo['proposed_actions'])}")

    rv = result["replay_verification"]
    print(f"\nReplay: {'PASS' if rv['match'] else 'FAIL'} ({rv['reason']})")
    print(f"  Hash: {rv['runtime_hash'][:16]}... WAL: {rv['wal_length']}")

    me = result.get("memory_evolution")
    if me:
        print(f"\nMemory Evolution:")
        print(f"  Success: {me['success_pattern'][:60]}")
        if me['failure_pattern']:
            print(f"  Failure: {me['failure_pattern'][:60]}")
        if me['avoid_next_time']:
            print(f"  Avoid:   {me['avoid_next_time'][:60]}")
        if me['reuse_next_time']:
            print(f"  Reuse:   {me['reuse_next_time'][:60]}")
        if me['policy_adjustments']:
            print(f"  Adjustments: {len(me['policy_adjustments'])}")

    final = result["final_state"]
    all_pass = rv["match"] and final == "DONE"
    print("\n" + "=" * 60)
    print(f"MCR COGNITIVE OS v0.2 {'PASS' if all_pass else 'RESULT'}")
    if final == "STOP":
        print("(stopped — risk too high or all tasks blocked)")
    elif final == "ASK_OWNER" or result.get("ask_owner"):
        print("(paused — waiting for owner approval)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="MCR Cognitive OS v0.2")
    parser.add_argument("--task", type=str, default=None)
    parser.add_argument("--stdin", action="store_true", default=False)
    args = parser.parse_args()

    if args.task:
        mode, task_text = "task", args.task
    elif args.stdin:
        mode, task_text = "stdin", None
    else:
        mode, task_text = "default", None

    result = run_cognitive_loop(mode=mode, task_text=task_text)
    print_result(result)

    final = result["final_state"]
    if final == "DONE" and result["replay_verification"]["match"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
