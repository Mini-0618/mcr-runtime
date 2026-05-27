"""
test_mcr_cognitive_os_v0.py — Tests for MCR Cognitive OS v0.1

Verifies each cognitive module independently and the full loop integration.
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure experiment modules are importable
_experiment_dir = Path(__file__).resolve().parents[1] / "experiments" / "mcr_cognitive_os_v0"
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_experiment_dir))
sys.path.insert(0, str(_project_root))

from state_reader import StateReader
from attention_filter import AttentionFilter
from task_scorer import TaskScorer
from goal_manager import GoalManager
from policy_engine import PolicyEngine, PolicyVerdict
from planner import Planner
from action_selector import ActionSelector
from reflection_engine import ReflectionEngine
from memory_writer import MemoryWriter


@pytest.fixture
def sample_tasks():
    return [
        {"id": "t1", "title": "Fix bug", "priority": 0.8, "risk": 0.2, "token_cost": 300,
         "urgency": 0.7, "category": "bugfix", "requires_owner": False, "status": "pending"},
        {"id": "t2", "title": "Deploy prod", "priority": 0.9, "risk": 0.9, "token_cost": 200,
         "urgency": 0.3, "category": "release", "requires_owner": True, "status": "pending"},
        {"id": "t3", "title": "Delete data", "priority": 0.1, "risk": 1.0, "token_cost": 50,
         "urgency": 0.1, "category": "destructive", "requires_owner": True, "status": "pending"},
        {"id": "t4", "title": "Write docs", "priority": 0.6, "risk": 0.1, "token_cost": 800,
         "urgency": 0.4, "category": "documentation", "requires_owner": False, "status": "pending"},
        {"id": "t5", "title": "Done task", "priority": 0.5, "risk": 0.1, "token_cost": 100,
         "urgency": 0.9, "category": "maintenance", "requires_owner": False, "status": "done"},
    ]


# ── StateReader ──

def test_state_reader_loads_tasks(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(json.dumps({"tasks": [{"id": "x", "status": "pending"}]}))
    reader = StateReader(str(tasks_file))
    result = reader.perceive()
    assert result["task_count"] == 1
    assert result["pending_count"] == 1


def test_state_reader_missing_file(tmp_path):
    reader = StateReader(str(tmp_path / "nonexistent.json"))
    result = reader.perceive()
    assert result["task_count"] == 0


# ── AttentionFilter ──

def test_attention_filter_filters_low_urgency(sample_tasks):
    attn = AttentionFilter(urgency_threshold=0.3)
    result = attn.filter(sample_tasks)
    ids = [t["id"] for t in result]
    assert "t1" in ids  # urgency 0.7
    assert "t2" in ids  # urgency 0.3 (edge)
    assert "t3" not in ids  # urgency 0.1
    assert "t5" not in ids  # status "done"


def test_attention_filter_explain(sample_tasks):
    attn = AttentionFilter(urgency_threshold=0.3)
    assert "PASSED" in attn.explain(sample_tasks[0])
    assert "FILTERED" in attn.explain(sample_tasks[2])


# ── TaskScorer ──

def test_task_scorer_scores(sample_tasks):
    scorer = TaskScorer()
    scored = scorer.score(sample_tasks[:2])
    assert all("score" in t for t in scored)
    assert all(0 <= t["score"] <= 1 for t in scored)


def test_task_scorer_rank(sample_tasks):
    scorer = TaskScorer()
    scored = scorer.score(sample_tasks[:4])
    ranked = scorer.rank(scored)
    for i in range(len(ranked) - 1):
        assert ranked[i]["score"] >= ranked[i + 1]["score"]


def test_task_scorer_prefers_high_priority_low_risk():
    scorer = TaskScorer()
    high_pri_low_risk = {"id": "a", "priority": 0.9, "risk": 0.1, "token_cost": 100}
    low_pri_high_risk = {"id": "b", "priority": 0.1, "risk": 0.9, "token_cost": 100}
    scored = scorer.score([high_pri_low_risk, low_pri_high_risk])
    assert scored[0]["score"] > scored[1]["score"]


# ── GoalManager ──

def test_goal_manager_set_and_check():
    gm = GoalManager()
    gm.set_goal("stability")
    aligned = {"category": "bugfix"}
    not_aligned = {"category": "release"}
    assert gm.check_alignment(aligned)
    assert not gm.check_alignment(not_aligned)


def test_goal_manager_history():
    gm = GoalManager()
    gm.set_goal("stability")
    gm.set_goal("performance")
    assert len(gm.goal_history) == 1


# ── PolicyEngine ──

def test_policy_blocks_destructive():
    policy = PolicyEngine()
    task = {"id": "x", "category": "destructive", "risk": 0.5, "requires_owner": False}
    verdict = policy.check(task)
    assert verdict.status == PolicyVerdict.BLOCKED


def test_policy_flags_owner_required():
    policy = PolicyEngine()
    task = {"id": "x", "category": "release", "risk": 0.5, "requires_owner": True}
    verdict = policy.check(task)
    assert verdict.status == PolicyVerdict.REQUIRES_OWNER


def test_policy_allows_safe_task():
    policy = PolicyEngine()
    task = {"id": "x", "category": "bugfix", "risk": 0.3, "requires_owner": False}
    verdict = policy.check(task)
    assert verdict.status == PolicyVerdict.ALLOWED


def test_policy_blocks_high_risk():
    policy = PolicyEngine()
    task = {"id": "x", "category": "bugfix", "risk": 0.95, "requires_owner": False}
    verdict = policy.check(task)
    assert verdict.status == PolicyVerdict.BLOCKED


def test_policy_filter_allowed(sample_tasks):
    policy = PolicyEngine()
    allowed = policy.filter_allowed(sample_tasks)
    for t in allowed:
        assert t["category"] != "destructive"
        assert t["risk"] <= 0.85


# ── Planner ──

def test_planner_generates_plan(sample_tasks):
    planner = Planner()
    plan = planner.plan(sample_tasks[:3], max_actions=2)
    assert len(plan) == 2
    assert all("task_id" in a for a in plan)
    assert all("action_type" in a for a in plan)


def test_planner_respects_max_actions(sample_tasks):
    planner = Planner()
    plan = planner.plan(sample_tasks, max_actions=1)
    assert len(plan) == 1


# ── ActionSelector ──

def test_action_selector_picks_first():
    selector = ActionSelector()
    plan = [{"title": "A", "score": 0.9}, {"title": "B", "score": 0.5}]
    result = selector.select_next(plan)
    assert result["title"] == "A"


def test_action_selector_empty_plan():
    selector = ActionSelector()
    assert selector.select_next([]) is None


# ── ReflectionEngine ──

def test_reflection_good_choice():
    reflector = ReflectionEngine()
    action = {"title": "Fix bug", "score": 0.8}
    ref = reflector.reflect(action, "allowed", 5, 3)
    assert ref["was_good_choice"] is True
    assert "Good" in ref["lesson"]


def test_reflection_blocked():
    reflector = ReflectionEngine()
    ref = reflector.reflect({}, "blocked", 5, 3)
    assert ref["was_good_choice"] is False
    assert "blocked" in ref["lesson"].lower()


def test_reflection_should_write():
    reflector = ReflectionEngine()
    ref = reflector.reflect({"score": 0.5}, "allowed", 1, 1)
    assert reflector.should_write_to_memory(ref) is True


# ── MemoryWriter ──

def test_memory_writer_stores_and_verifies(tmp_path):
    wal_path = str(tmp_path / "test_wal.jsonl")
    mem = MemoryWriter(wal_path=wal_path)
    mem.store_reflection({"lesson": "test"}, "cycle1")
    mem.store_action({"title": "test_action"}, "cycle1")
    result = mem.verify_replay()
    assert result["match"] is True
    assert result["reason"] == "ok"
    assert result["wal_length"] == 2


def test_memory_writer_empty_wal(tmp_path):
    wal_path = str(tmp_path / "empty_wal.jsonl")
    mem = MemoryWriter(wal_path=wal_path)
    result = mem.verify_replay()
    assert result["match"] is True


# ── Full Loop Integration ──

def test_full_cognitive_loop(tmp_path):
    """Integration test: run the full cognitive loop with isolated WAL."""
    import run_cognitive_loop as rcl
    # Use a fresh WAL in temp dir to avoid contamination from previous runs
    wal_path = str(tmp_path / "test_wal.jsonl")
    mem = rcl.MemoryWriter(wal_path=wal_path)

    # Run the cognitive loop logic inline with the clean WAL
    cycle_id = "test_cycle"
    tasks_path = str(rcl._experiment_dir / "tasks.json")
    reader = rcl.StateReader(tasks_path)
    perception = reader.perceive()
    attn = rcl.AttentionFilter(urgency_threshold=0.3)
    attended = attn.filter(perception["tasks"])
    scorer = rcl.TaskScorer()
    scored = scorer.score(attended)
    ranked = scorer.rank(scored)
    policy = rcl.PolicyEngine()
    allowed = [t for t in ranked if policy.check(t).status == rcl.PolicyVerdict.ALLOWED]
    planner = rcl.Planner()
    plan = planner.plan(allowed, max_actions=3)
    selector = rcl.ActionSelector()
    next_action = selector.select_next(plan)
    reflector = rcl.ReflectionEngine()
    reflection = reflector.reflect(action=next_action or {}, policy_verdict="allowed",
                                   task_count=perception["task_count"], attended_count=len(attended))
    mem.store_action(next_action or {"title": "no_action"}, cycle_id)
    mem.store_reflection(reflection, cycle_id)
    verify_result = mem.verify_replay()

    assert verify_result["match"] is True
    assert perception["task_count"] > 0
    assert len(attended) >= 0
    assert next_action is not None
    assert reflection["was_good_choice"] is True


# ── InputAdapter ──

def test_text_to_task_basic():
    from input_adapter import text_to_task
    task = text_to_task("Fix the login bug")
    assert task["title"] == "Fix the login bug"
    assert task["category"] == "bugfix"
    assert task["status"] == "pending"
    assert task["source"] == "cli"
    assert task["requires_owner"] is False


def test_text_to_task_high_risk_keywords():
    from input_adapter import text_to_task
    # merge → requires_owner
    t1 = text_to_task("Merge cognitive OS into main")
    assert t1["requires_owner"] is True

    # delete → requires_owner + destructive
    t2 = text_to_task("Delete the archive directory")
    assert t2["requires_owner"] is True

    # deploy → requires_owner
    t3 = text_to_task("Deploy to production server")
    assert t3["requires_owner"] is True

    # secret → requires_owner
    t4 = text_to_task("Read the secret API key")
    assert t4["requires_owner"] is True

    # browser → requires_owner
    t5 = text_to_task("Open browser and login")
    assert t5["requires_owner"] is True


def test_text_to_task_safe_task():
    from input_adapter import text_to_task
    task = text_to_task("Write documentation for the API")
    assert task["requires_owner"] is False
    assert task["category"] == "documentation"


def test_text_to_task_empty_raises():
    from input_adapter import text_to_task
    with pytest.raises(ValueError):
        text_to_task("")


def test_text_to_tasks_multiline():
    from input_adapter import text_to_tasks
    text = "Fix bug A\nWrite docs\nOptimize reducer"
    tasks = text_to_tasks(text)
    assert len(tasks) == 3
    assert tasks[0]["category"] == "bugfix"
    assert tasks[1]["category"] == "documentation"
    assert tasks[2]["category"] == "optimization"


def test_text_to_task_urgency_detection():
    from input_adapter import text_to_task
    urgent = text_to_task("Urgent fix needed now")
    normal = text_to_task("Check test coverage")
    later = text_to_task("Maybe refactor later someday")
    assert urgent["urgency"] > normal["urgency"]
    assert normal["urgency"] > later["urgency"]


def test_text_to_task_risk_estimation():
    from input_adapter import text_to_task
    safe = text_to_task("Write documentation")
    risky = text_to_task("Deploy and push to production")
    assert safe["risk"] < risky["risk"]


def test_format_task_report():
    from input_adapter import text_to_task, format_task_report
    task = text_to_task("Fix the bug")
    report = format_task_report(task)
    assert "Fix the bug" in report
    assert "Priority" in report
    assert "Risk" in report


# ── CLI Mode Integration ──

def test_cognitive_loop_default_mode():
    """Default mode reads tasks.json."""
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="default")
    assert result["input_mode"] == "default"
    assert result["perception"]["task_count"] > 0
    assert result["replay_verification"]["match"] is True


def test_cognitive_loop_cli_task_mode():
    """CLI mode accepts a single task string."""
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Check MCR current status")
    assert result["input_mode"] == "task"
    assert result["perception"]["task_count"] == 1
    assert result["replay_verification"]["match"] is True


def test_cognitive_loop_high_risk_task_asks_owner():
    """High-risk CLI task should be blocked or require owner."""
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Merge into main and push")
    # Should NOT be freely allowed — either blocked (too risky) or needs owner
    assert result["policy"]["allowed"] == 0


def test_cognitive_loop_safe_task_allowed():
    """Safe CLI task should be allowed."""
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Write tests for reducer")
    assert result["policy"]["allowed"] >= 1
    assert result["replay_verification"]["match"] is True


def test_cognitive_loop_stdin_mode(monkeypatch):
    """Stdin mode reads from stdin."""
    import run_cognitive_loop as rcl
    monkeypatch.setattr("sys.stdin", type("FakeStdin", (), {
        "read": lambda self: "Check if tests pass\nReview code quality",
        "isatty": lambda self: False,
    })())
    result = rcl.run_cognitive_loop(mode="stdin")
    assert result["input_mode"] == "stdin"
    assert result["perception"]["task_count"] == 2
    assert result["replay_verification"]["match"] is True


def test_latest_run_json_generated():
    """latest_run.json should be created after a run."""
    import run_cognitive_loop as rcl
    latest_run = rcl._experiment_dir / "logs" / "latest_run.json"
    rcl.run_cognitive_loop(mode="task", task_text="Quick test task")
    assert latest_run.exists()
    data = json.loads(latest_run.read_text())
    assert "cycle_id" in data
    assert "replay_verification" in data
