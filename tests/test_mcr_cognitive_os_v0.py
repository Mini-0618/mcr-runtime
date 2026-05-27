"""
test_mcr_cognitive_os_v0.py — Tests for MCR Cognitive OS v0.1 + v0.2
"""
import json
import sys
from pathlib import Path

import pytest

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
from input_adapter import text_to_task, text_to_tasks
from state_machine import StateMachine, StateMachineError
from memory_blocks import MemoryBlocks
from browser_operator import MockBrowserOperator, PageState, ActionResult


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


# ── v0.1 Module Tests ──

def test_state_reader_loads_tasks(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(json.dumps({"tasks": [{"id": "x", "status": "pending"}]}))
    reader = StateReader(str(tasks_file))
    result = reader.perceive()
    assert result["task_count"] == 1

def test_state_reader_missing_file(tmp_path):
    reader = StateReader(str(tmp_path / "nonexistent.json"))
    assert reader.perceive()["task_count"] == 0

def test_attention_filter_filters_low_urgency(sample_tasks):
    attn = AttentionFilter(urgency_threshold=0.3)
    result = attn.filter(sample_tasks)
    ids = [t["id"] for t in result]
    assert "t1" in ids
    assert "t3" not in ids

def test_task_scorer_rank(sample_tasks):
    scorer = TaskScorer()
    scored = scorer.score(sample_tasks[:4])
    ranked = scorer.rank(scored)
    for i in range(len(ranked) - 1):
        assert ranked[i]["score"] >= ranked[i + 1]["score"]

def test_policy_blocks_destructive():
    policy = PolicyEngine()
    task = {"id": "x", "category": "destructive", "risk": 0.5, "requires_owner": False}
    assert policy.check(task).status == PolicyVerdict.BLOCKED

def test_policy_flags_owner_required():
    policy = PolicyEngine()
    task = {"id": "x", "category": "release", "risk": 0.5, "requires_owner": True}
    assert policy.check(task).status == PolicyVerdict.REQUIRES_OWNER

def test_policy_allows_safe_task():
    policy = PolicyEngine()
    task = {"id": "x", "category": "bugfix", "risk": 0.3, "requires_owner": False}
    assert policy.check(task).status == PolicyVerdict.ALLOWED

def test_planner_generates_plan(sample_tasks):
    plan = Planner().plan(sample_tasks[:3], max_actions=2)
    assert len(plan) == 2

def test_action_selector_picks_first():
    plan = [{"title": "A", "score": 0.9}, {"title": "B", "score": 0.5}]
    assert ActionSelector().select_next(plan)["title"] == "A"

def test_reflection_good_choice():
    ref = ReflectionEngine().reflect({"title": "Fix", "score": 0.8}, "allowed", 5, 3)
    assert ref["was_good_choice"] is True

def test_memory_writer_stores_and_verifies(tmp_path):
    mem = MemoryWriter(wal_path=str(tmp_path / "wal.jsonl"))
    mem.store_reflection({"lesson": "test"}, "c1")
    mem.store_action({"title": "act"}, "c1")
    assert mem.verify_replay()["match"] is True


# ── InputAdapter Tests ──

def test_text_to_task_basic():
    task = text_to_task("Fix the login bug")
    assert task["category"] == "bugfix"
    assert task["requires_owner"] is False

def test_text_to_task_high_risk_keywords():
    assert text_to_task("Merge into main")["requires_owner"] is True
    assert text_to_task("Delete archive")["requires_owner"] is True
    assert text_to_task("Deploy to production")["requires_owner"] is True

def test_text_to_task_empty_raises():
    with pytest.raises(ValueError):
        text_to_task("")

def test_text_to_tasks_multiline():
    tasks = text_to_tasks("Fix bug A\nWrite docs")
    assert len(tasks) == 2


# ── v0.2 StateMachine Tests ──

def test_state_machine_starts_at_intake():
    sm = StateMachine()
    assert sm.current() == "INTAKE"
    assert not sm.is_terminal()

def test_state_machine_valid_transition():
    sm = StateMachine()
    sm.transition("READ_STATE", "loaded")
    assert sm.current() == "READ_STATE"

def test_state_machine_invalid_transition():
    sm = StateMachine()
    with pytest.raises(StateMachineError):
        sm.transition("DONE", "skip all")

def test_state_machine_full_trace():
    sm = StateMachine()
    sm.transition("READ_STATE", "r1")
    sm.transition("ATTENTION", "r2")
    trace = sm.get_trace()
    assert len(trace) == 3
    assert trace[0]["state"] == "INTAKE"
    assert trace[2]["state"] == "ATTENTION"

def test_state_machine_terminal():
    sm = StateMachine()
    sm.transition("READ_STATE", "")
    sm.transition("ATTENTION", "")
    sm.transition("SCORE", "")
    sm.transition("POLICY", "")
    sm.transition("STOP", "risk too high")
    assert sm.is_terminal()
    assert sm.current() == "STOP"


# ── v0.2 MemoryBlocks Tests ──

def test_memory_blocks_default_persona():
    blocks = MemoryBlocks()
    assert blocks.persona["name"] == "MCR Cognitive OS"
    assert len(blocks.persona["boundaries"]) > 0

def test_memory_blocks_update_context():
    blocks = MemoryBlocks()
    blocks.update_context("task_count", 5)
    assert blocks.context["task_count"] == 5

def test_memory_blocks_add_knowledge():
    blocks = MemoryBlocks()
    blocks.add_knowledge("Always check risk first", source="test", confidence=0.9)
    assert len(blocks.knowledge) == 1
    assert blocks.knowledge[0]["lesson"] == "Always check risk first"

def test_memory_blocks_persona_boundary():
    blocks = MemoryBlocks()
    # "修改 Runtime" should violate "不修改 Runtime 核心"
    assert blocks.check_persona_boundary("修改 Runtime 核心代码") is False
    # "写文档" should be fine
    assert blocks.check_persona_boundary("写文档") is True

def test_memory_blocks_to_dict():
    blocks = MemoryBlocks()
    blocks.update_context("x", 1)
    blocks.add_knowledge("lesson1")
    d = blocks.to_dict()
    assert "persona" in d
    assert "context" in d
    assert "knowledge" in d
    assert d["context"]["x"] == 1

def test_memory_blocks_save_load(tmp_path):
    path = str(tmp_path / "blocks.json")
    blocks = MemoryBlocks()
    blocks.update_context("key", "val")
    blocks.add_knowledge("lesson")
    blocks.save(path)
    loaded = MemoryBlocks.load(path)
    assert loaded.context["key"] == "val"
    assert len(loaded.knowledge) == 1


# ── v0.2 MockBrowserOperator Tests ──

def test_mock_browser_observe():
    op = MockBrowserOperator()
    page = op.observe()
    assert isinstance(page, PageState)
    assert page.url == "https://example.com/mock"
    assert len(page.elements) == 4

def test_mock_browser_propose_actions():
    op = MockBrowserOperator()
    actions = op.propose_actions("Click the submit button")
    assert len(actions) > 0
    assert any(a["action"] == "click" for a in actions)

def test_mock_browser_propose_actions_observe():
    op = MockBrowserOperator()
    actions = op.propose_actions("Check the page status")
    assert any(a["action"] == "observe" for a in actions)

def test_mock_browser_execute_mock_click():
    op = MockBrowserOperator()
    result = op.execute_mock({"action": "click", "target": 0})
    assert result.success is True
    assert "click" in result.action

def test_mock_browser_execute_mock_navigate():
    op = MockBrowserOperator()
    result = op.execute_mock({"action": "navigate", "url": "https://test.com"})
    assert result.success is True
    assert op.observe().url == "https://test.com"

def test_mock_browser_no_real_browser():
    """Verify MockBrowserOperator has no network/import dependencies."""
    import inspect
    source = inspect.getsource(MockBrowserOperator)
    assert "playwright" not in source.lower()
    assert "selenium" not in source.lower()
    assert "requests" not in source.lower()
    assert "urllib" not in source.lower()


# ── v0.2 Full Loop Integration Tests ──

def test_state_trace_exists():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Write tests")
    assert "state_trace" in result
    assert len(result["state_trace"]) > 0
    states = [s["state"] for s in result["state_trace"]]
    assert "INTAKE" in states
    assert "DONE" in states

def test_state_machine_enters_done():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Fix the bug")
    assert result["final_state"] == "DONE"

def test_high_risk_enters_ask_owner_or_stop():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Merge into main and push")
    assert result["final_state"] in ("ASK_OWNER", "STOP")

def test_merge_push_delete_deploy_enters_ask_owner():
    import run_cognitive_loop as rcl
    for keyword in ["merge", "push", "delete", "deploy"]:
        result = rcl.run_cognitive_loop(mode="task", task_text=f"{keyword} the code")
        states = [s["state"] for s in result["state_trace"]]
        assert "ASK_OWNER" in states or "STOP" in states, f"'{keyword}' should trigger ASK_OWNER or STOP"

def test_memory_blocks_in_output():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Review code")
    assert "memory_blocks" in result
    mb = result["memory_blocks"]
    assert "persona" in mb
    assert "context" in mb
    assert "knowledge" in mb

def test_browser_observation_in_output():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Check the website")
    assert "browser_observation" in result
    bo = result["browser_observation"]
    assert bo is not None
    assert "page" in bo
    assert "proposed_actions" in bo

def test_replay_verification_pass():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Write documentation")
    assert result["replay_verification"]["match"] is True

def test_task_mode_still_works():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Optimize the reducer")
    assert result["input_mode"] == "task"
    assert result["perception"]["task_count"] == 1

def test_stdin_mode_still_works(monkeypatch):
    import run_cognitive_loop as rcl
    monkeypatch.setattr("sys.stdin", type("S", (), {
        "read": lambda self: "Check test coverage",
        "isatty": lambda self: False,
    })())
    result = rcl.run_cognitive_loop(mode="stdin")
    assert result["input_mode"] == "stdin"
    assert result["perception"]["task_count"] == 1

def test_latest_run_json_generated():
    import run_cognitive_loop as rcl
    rcl.run_cognitive_loop(mode="task", task_text="Quick test")
    path = rcl._experiment_dir / "logs" / "latest_run.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "state_trace" in data
    assert "memory_blocks" in data
    assert "browser_observation" in data


# ── v0.2 MemoryEvolution Tests ──

def test_memory_evolution_success_pattern():
    from memory_evolution import MemoryEvolution
    evolver = MemoryEvolution()
    run = {
        "reflection": {"lesson": "Good selection", "was_good_choice": True},
        "policy": {"allowed": 3, "blocked": 0, "requires_owner": 0},
        "execution": {"success": True, "output": "Done"},
        "final_state": "DONE",
        "scoring": {"top_task": "Fix bug", "top_score": 0.8},
        "attention": {"attended_count": 5, "filtered_count": 1},
    }
    record = evolver.evolve(run)
    assert record.success_pattern != ""
    assert record.reuse_next_time != ""
    assert record.confidence > 0.5

def test_memory_evolution_failure_pattern():
    from memory_evolution import MemoryEvolution
    evolver = MemoryEvolution()
    run = {
        "reflection": {"lesson": "Action blocked by policy", "was_good_choice": False},
        "policy": {"allowed": 0, "blocked": 3, "requires_owner": 0},
        "execution": {"success": False, "output": "Blocked"},
        "final_state": "STOP",
        "scoring": {"top_task": "Deploy", "top_score": 0.3},
        "attention": {"attended_count": 3, "filtered_count": 0},
    }
    record = evolver.evolve(run)
    assert record.failure_pattern != ""
    assert record.avoid_next_time != ""

def test_memory_evolution_policy_adjustments():
    from memory_evolution import MemoryEvolution
    evolver = MemoryEvolution()
    run = {
        "reflection": {"lesson": "blocked", "was_good_choice": False},
        "policy": {"allowed": 1, "blocked": 5, "requires_owner": 0},
        "execution": None,
        "final_state": "STOP",
        "scoring": {"top_task": "?", "top_score": 0},
        "attention": {"attended_count": 2, "filtered_count": 8},
    }
    record = evolver.evolve(run)
    assert len(record.policy_adjustments) > 0

def test_memory_evolution_to_dict():
    from memory_evolution import MemoryEvolution, EvolutionRecord
    record = EvolutionRecord(success_pattern="test", failure_pattern="fail")
    d = record.to_dict()
    assert d["success_pattern"] == "test"
    assert d["failure_pattern"] == "fail"

def test_memory_evolution_in_cognitive_loop():
    import run_cognitive_loop as rcl
    result = rcl.run_cognitive_loop(mode="task", task_text="Write tests")
    assert "memory_evolution" in result
    me = result["memory_evolution"]
    assert me is not None
    assert "success_pattern" in me
