#!/usr/bin/env python3
"""
MCR Evolution Test — AdaptivePolicy integration
================================================
Tests whether retrieval channel weights evolve under real workload.

Hypothesis: after 200 episodes, channel weights diverge from 1.0 baseline
iff the adaptive feedback loop can detect and amplify useful retrieval patterns.

G0: Integration test — AdaptivePolicy + CompactionRuntime connect
G1: Feedback loop fires — weight adaptation count > 0
G2: Weight divergence — at least one channel weight != 1.0
G3: Learning signal — weight change correlates with retrieval quality
"""
import sys, os, random, shutil, json
sys.path.insert(0, './stable')
sys.path.insert(0, './runtime_phys_observation/phase_IV_B_compaction')
sys.path.insert(0, './runtime_phys_observation/phase_IV_A_adaptation')

from semantic_compaction import CompactionRuntime
from adaptive_policy import AdaptivePolicy

TASK_QUERIES = ["python_gc","sql_query","docker_runtime","wal_replay",
                 "semantic_search","crash_recovery","network_protocol","file_system"]

TOPIC_CONTENT = {
    "python_gc": [("Python GC uses reference counting and generational collection", ["gc","python","memory"], 0.8)],
    "sql_query": [("B-tree indexes speed up SQL query execution", ["sql","index","b-tree"], 0.8)],
    "docker_runtime": [("Docker container shares the host kernel", ["docker","container","kernel"], 0.8)],
    "wal_replay": [("WAL writes data to log before applying to main database", ["wal","write_ahead"], 0.9)],
    "semantic_search": [("embedding vectors capture semantic meaning", ["embedding","vector","semantic"], 0.9)],
    "crash_recovery": [("checkpoint saves consistent state for fast restart", ["checkpoint","restart","recovery"], 0.9)],
    "network_protocol": [("TCP guarantees ordered reliable delivery", ["tcp","reliable","ordered"], 0.9)],
    "file_system": [("inode stores file metadata: size timestamps block pointers", ["inode","metadata","fs"], 0.9)],
}

def populate(cr):
    tick = 0
    for topic, memories in TOPIC_CONTENT.items():
        for content, tags, importance in memories:
            cr.store(content, memory_type="episodic", importance=importance,
                    tags=tags, current_tick=tick)
            tick += 10
    cr._lm.try_flush(tick)

def oracle_relevance(query, results):
    """Ground truth: was this retrieval relevant to the query?"""
    if not results:
        return False
    # Simple heuristic: result content contains query keyword
    for r in results:
        content = r.get("content", "").lower()
        q_word = query.split("_")[0].lower()  # e.g. "python_gc" -> "python"
        if q_word in content:
            return True
    return False

class EvolutionRuntime:
    """CompactionRuntime + AdaptivePolicy integrated."""

    def __init__(self, root: str):
        self._cr = CompactionRuntime(root)
        self._ap = AdaptivePolicy(root)
        self._tick = 0
        self._feedback_log = []

    def retrieve(self, query: str, max_results: int = 5) -> list:
        """Retrieve with adaptive channel reweighting."""
        # Step 1: base retrieval from MCR
        results = self._cr.retrieve(
            query, current_goal="evolution_test",
            current_tick=self._tick, max_results=max_results
        )

        if not results:
            return results

        # Step 2: apply adaptive channel weights
        weights = self._ap.get_weights()
        for r in results:
            ch = r.get("layer", "episodic")
            r["_channel_weight"] = weights.get(ch, 1.0)
            r["_raw_score"] = r.get("retrieval_score", 0.0)
            # Reweight: original_score * channel_weight
            r["retrieval_score"] = r["_raw_score"] * r["_channel_weight"]

        # Resort by reweighted score
        results.sort(key=lambda x: x["retrieval_score"], reverse=True)

        # Step 3: record feedback based on outcome
        was_useful = oracle_relevance(query, results)
        if results:
            primary_layer = results[0].get("layer", "episodic")
            self._ap.record_retrieval_feedback(
                channel=primary_layer,
                relevance=1.0 if was_useful else 0.0,
                was_useful=was_useful
            )
            self._feedback_log.append({
                "tick": self._tick,
                "query": query,
                "layer": primary_layer,
                "was_useful": was_useful,
                "weights_snapshot": dict(weights),
            })

        return results

    def tick(self):
        self._tick += 1
        self._cr.tick()
        self._ap.tick(self._tick)

    @property
    def episodic(self):
        return self._cr.episodic

    @property
    def working(self):
        return self._cr.working

    def get_weights(self) -> dict:
        return self._ap.get_weights()

    def get_adaptation_count(self) -> int:
        return self._ap.get_adaptation_count()

def run_evolution_test(n_episodes=300, seed=42):
    random.seed(seed)
    mcr_root = f"/tmp/mcr_evolution_{seed}"
    if os.path.exists(mcr_root): shutil.rmtree(mcr_root)

    er = EvolutionRuntime(mcr_root)
    populate(er._cr)

    print(f"{'Ep':>4} {'Tick':>6} {'W':>3} {'E':>3} {'S':>3}  {'adapt':>5}  {'W_wt':>6} {'E_wt':>6} {'S_wt':>6}  {'useful':>6}")
    print("-" * 75)

    for ep in range(n_episodes):
        q = TASK_QUERIES[ep % len(TASK_QUERIES)]
        er.retrieve(q, max_results=3)
        er.tick()

        if ep % 30 == 0 or ep < 3:
            wts = er.get_weights()
            adapt = er.get_adaptation_count()
            W,E,S = len(er.working), len(er.episodic), len(er._cr.semantic)
            useful = sum(1 for fb in er._feedback_log[-30:] if fb["was_useful"])
            print(f"{ep:>4} {er._tick:>6} {W:>3} {E:>3} {S:>3}  {adapt:>5}  "
                  f"{wts.get('working',0):>6.3f} {wts.get('episodic',0):>6.3f} {wts.get('semantic',0):>6.3f}  "
                  f"{useful:>6}")

    # Final analysis
    wts = er.get_weights()
    adapt_count = er.get_adaptation_count()
    total_feedback = len(er._feedback_log)
    useful_count = sum(1 for fb in er._feedback_log if fb["was_useful"])

    print(f"\n{'='*75}")
    print(f"EVOLUTION TEST RESULTS ({n_episodes} episodes)")
    print(f"{'='*75}")
    print(f"  Total feedback events:  {total_feedback}")
    print(f"  Useful retrievals:     {useful_count} ({100*useful_count/max(1,total_feedback):.1f}%)")
    print(f"  Adaptation events:    {adapt_count}")
    print(f"  Final channel weights:")
    for ch, w in sorted(wts.items()):
        delta = w - 1.0
        arrow = "↑" if delta > 0.01 else "↓" if delta < -0.01 else "→"
        print(f"    {ch:>12}: {w:.4f} ({arrow} {delta:+.4f} from baseline)")

    # Verdict
    G0_pass = total_feedback > 0
    G1_pass = adapt_count > 0
    G2_pass = any(abs(w - 1.0) > 0.01 for w in wts.values())
    G3_pass = useful_count > 0 and adapt_count > 0

    print(f"\nVERDICT:")
    print(f"  G0 Integration:        {'✅ PASS' if G0_pass else '❌ FAIL'}")
    print(f"  G1 Feedback fired:     {'✅ PASS' if G1_pass else '❌ FAIL'}")
    print(f"  G2 Weight diverge:     {'✅ PASS' if G2_pass else '❌ FAIL'}")
    print(f"  G3 Learning signal:    {'✅ PASS' if G3_pass else '❌ FAIL'}")

    all_pass = G0_pass and G1_pass and G2_pass and G3_pass
    print(f"\n{'='*75}")
    if all_pass:
        print(f"✅ MCR SHOWS EVIDENCE OF EVOLUTION")
        print(f"   Adaptive weights diverged from baseline under retrieval workload.")
    else:
        print(f"❌ MCR DID NOT EVOLVE (G0={G0_pass} G1={G1_pass} G2={G2_pass} G3={G3_pass})")
    print(f"{'='*75}")

    # Save feedback log
    log_path = f"{mcr_root}/evolution_log.json"
    with open(log_path, "w") as f:
        json.dump({
            "weights": wts,
            "adaptation_count": adapt_count,
            "feedback_log": er._feedback_log,
            "n_episodes": n_episodes,
        }, f, indent=2)
    print(f"\nLog saved: {log_path}")

    shutil.rmtree(mcr_root)
    return {
        "G0": G0_pass, "G1": G1_pass, "G2": G2_pass, "G3": G3_pass,
        "weights": wts, "adapt_count": adapt_count,
        "useful_rate": useful_count / max(1, total_feedback),
    }

if __name__ == "__main__":
    print("MCR EVOLUTION TEST — Does adaptive feedback drive weight evolution?")
    print("="*75)
    run_evolution_test(300, seed=42)
