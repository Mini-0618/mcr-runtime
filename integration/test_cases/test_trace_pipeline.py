from pathlib import Path
"""Test trace pipeline append-only property."""
import sys, json, tempfile, shutil
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "observability" / "traces"))
from trace_pipeline import TracePipeline

def test_trace_append_only():
    """Traces must append without overwrite."""
    tmpdir = tempfile.mkdtemp()
    try:
        tp = TracePipeline(base_dir=tmpdir)
        tp.tick(tick=1, latency=0.04, retrieval_count=3, semantic_ratio=0.15)
        tp.tick(tick=2, latency=0.05, retrieval_count=5, semantic_ratio=0.20)

        # Read back
        log_file = list(Path(tmpdir).rglob("*.jsonl"))[0]
        lines = open(log_file).readlines()
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        assert r1["tick"] == 1
        assert r2["tick"] == 2
        print(f"[PASS] Append-only verified: {len(lines)} records")
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    test_trace_append_only()
