"""
test_mcr_auto_v0.py — Tests for MCR-Auto v0.1

Verifies the Cognitive OS → Auto execution loop integration.
"""
import json
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parents[1]
_experiment_dir = _project_root / "experiments" / "mcr_cognitive_os_v0"
_auto_dir = _project_root / "experiments" / "mcr_auto_v0"
sys.path.insert(0, str(_experiment_dir))
sys.path.insert(0, str(_auto_dir))
sys.path.insert(0, str(_project_root))

from task_executor import MockTaskExecutor, ExecutionResult


# ── MockTaskExecutor Tests ──

def test_executor_investigate():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "investigate", "title": "Check code", "task_id": "t1"})
    assert result.success is True
    assert "Investigated" in result.output
    assert result.task_id == "t1"

def test_executor_fix():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "fix", "title": "Fix bug", "task_id": "t2"})
    assert result.success is True
    assert "Fixed" in result.output

def test_executor_write():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "write", "title": "Write docs", "task_id": "t3"})
    assert result.success is True
    assert "Wrote" in result.output

def test_executor_optimize():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "profile_and_optimize", "title": "Optimize", "task_id": "t4"})
    assert result.success is True
    assert "Profiled" in result.output

def test_executor_escalate():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "escalate", "title": "Merge main", "task_id": "t5"})
    assert result.success is False
    assert "ESCALATED" in result.output

def test_executor_generic():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "unknown", "title": "Something", "task_id": "t6"})
    assert result.success is True

def test_executor_result_to_dict():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "investigate", "title": "Test", "task_id": "t1"})
    d = result.to_dict()
    assert "success" in d
    assert "output" in d
    assert "duration_ms" in d

def test_executor_has_duration():
    ex = MockTaskExecutor()
    result = ex.execute({"action_type": "investigate", "title": "Test", "task_id": "t1"})
    assert result.duration_ms >= 0

def test_executor_no_real_browser():
    import inspect
    source = inspect.getsource(MockTaskExecutor)
    assert "playwright" not in source.lower()
    assert "selenium" not in source.lower()
    assert "requests" not in source.lower()


# ── Full Auto Loop Integration Tests ──

def test_auto_loop_default_mode():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Review code quality")
    assert result["loop_type"] == "auto"
    assert result["final_state"] == "DONE"
    assert result["replay_verification"]["match"] is True
    assert result["execution"] is not None
    assert result["execution"]["success"] is True

def test_auto_loop_high_risk_asks_owner():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Merge into main and push")
    assert result["final_state"] in ("ASK_OWNER", "STOP")
    if result.get("execution"):
        assert result["execution"]["success"] is False

def test_auto_loop_execution_in_result():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Fix the bug")
    assert "execution" in result
    assert result["execution"] is not None
    assert "output" in result["execution"]
    assert "success" in result["execution"]

def test_auto_loop_state_trace():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Write docs")
    states = [s["state"] for s in result["state_trace"]]
    assert "INTAKE" in states
    assert "REFLECT" in states
    assert "DONE" in states

def test_auto_loop_memory_blocks():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Optimize reducer")
    mb = result["memory_blocks"]
    assert "persona" in mb
    assert "context" in mb
    assert "knowledge" in mb
    assert mb["context"].get("loop_type") == "auto"

def test_auto_loop_browser_observation():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Check the website")
    assert "browser_observation" in result

def test_auto_loop_replay_pass():
    import run_auto_loop as ral
    result = ral.run_auto_loop(mode="task", task_text="Investigate test coverage")
    assert result["replay_verification"]["match"] is True

def test_auto_loop_stdin(monkeypatch):
    import run_auto_loop as ral
    monkeypatch.setattr("sys.stdin", type("S", (), {
        "read": lambda self: "Check MCR status",
        "isatty": lambda self: False,
    })())
    result = ral.run_auto_loop(mode="stdin")
    assert result["input_mode"] == "stdin"
    assert result["loop_type"] == "auto"

def test_auto_loop_latest_run_json():
    import run_auto_loop as ral
    ral.run_auto_loop(mode="task", task_text="Quick test")
    path = ral._experiment_dir / "logs" / "latest_run.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["loop_type"] == "auto"
    assert "execution" in data
