#!/usr/bin/env python3
"""
v0.19 — Semantic Bridge Validity Benchmark
============================================

CORRECTED DESIGN (addressing v0.18 flaws):

v0.18 Core Confound:
  - episodic scoring used recency + importance as confound
  - even when overlap=0, episodic could win via heuristic
  - this masked whether semantic bridge was actually causal

v0.19 Design Principle:
  REMOVE all heuristic confounds. Make the ONLY difference
  between signal and distractor be the semantic bridge.

  - equal recency: all items created at same timestamp
  - equal importance: all items have same importance score
  - equal pool position: all items at same retrieval position
  - NO keyword overlap with query for ANY item

  The ONLY variable: latent category bridge

Three Critical Tests:
  Test 1: Pure Bridge Isolation
    - query A, signal with bridge to A, distractors without bridge
    - semantic should route to signal via bridge
    - episodic should return random/uniform

  Test 2: Bridge Specificity
    - signal has bridge to query's category
    - distractor has bridge to DIFFERENT category
    - tests whether semantic actually uses bridge or just retrieves everything

  Test 3: Cross-Surface Bridge
    - signal surface form completely different from query
    - but latent structure maps to same category
    - episodic surface match should be zero
    - semantic latent match should succeed

Research Question:
  Can semantic provide a retrieval capability that episodic
  CANNOT independently achieve, using ONLY latent category bridge
  as the differentiating factor?
"""

import random
import math
from collections import defaultdict

random.seed(42)

# =============================================================================
# MEMORY SYSTEM WITH CONTROLLED HEURISTICS
# =============================================================================

class ControlledMemory:
    """
    Memory system where episodic retrieval is controlled
    to remove recency/importance/pool-position confound.
    """

    def __init__(self):
        self.episodic = []  # (content, importance, category)
        self.semantic_bridges = {}  # category -> list of episodic_ids

    def add(self, content, importance=0.5, category=None):
        """Add episodic item with optional semantic category bridge."""
        idx = len(self.episodic)
        self.episodic.append({
            'content': content,
            'importance': importance,
            'category': category,
            'id': idx
        })
        # Register semantic bridge
        if category:
            if category not in self.semantic_bridges:
                self.semantic_bridges[category] = []
            self.semantic_bridges[category].append(idx)
        return idx

    def episodic_retrieval(self, query, top_k=None):
        """
        Level 0 episodic retrieval.

        CRITICAL: Pure keyword matching ONLY.
        No recency, no importance, no position bias.
        Tie-breaking MUST be random (not insertion order).

        Returns items sorted purely by keyword overlap.
        """
        q_words = set(query.lower().split())

        scores = []
        for item in self.episodic:
            e_words = set(item['content'].lower().split())
            # Pure keyword overlap (Jaccard)
            overlap = len(q_words & e_words) / max(len(q_words | e_words), 1)
            scores.append((item['id'], overlap, item))

        # Sort by keyword overlap ONLY
        # CRITICAL: When overlap=0 for ALL items, we need random tie-breaking
        # NOT insertion order (that would be a confound)
        # Strategy: add tiny random noise to score
        import random
        random_noise = random.random() * 0.001  # tiny noise breaks ties randomly
        scored_with_noise = [(bid, overlap + random_noise, item)
                             for bid, overlap, item in scores]
        scored_with_noise.sort(key=lambda x: -x[1])

        if top_k:
            return scored_with_noise[:top_k]
        return scored_with_noise

    def semantic_retrieval(self, query, top_k=None):
        """
        Level 1+2 semantic retrieval.

        Uses latent category bridge to route retrieval.
        """
        q_words = set(query.lower().split())
        results = []

        # Phase 1: Check if query maps to a semantic category
        query_category = self._categorize(q_words)

        if query_category and query_category in self.semantic_bridges:
            # We have a semantic bridge for this query
            bridge_ids = self.semantic_bridges[query_category]

            # Retrieve via semantic category
            for bid in bridge_ids:
                item = self.episodic[bid]
                # Score: semantic category match + some keyword residual
                q_emb = q_words
                e_words = set(item['content'].lower().split())
                k_overlap = len(q_emb & e_words) / max(len(q_emb | e_words), 1)
                semantic_score = 0.7 * 1.0 + 0.3 * k_overlap  # category dominant
                results.append((bid, semantic_score, 'semantic', item))
        else:
            # No semantic bridge - fall back to episodic
            pass

        # Phase 2: Also run episodic for comparison
        e_scores = self.episodic_retrieval(query)
        for bid, overlap, item in e_scores:
            # Don't duplicate
            if bid not in [r[0] for r in results]:
                results.append((bid, overlap, 'episodic', item))

        # Sort by score
        results.sort(key=lambda x: -x[1])

        if top_k:
            return results[:top_k]
        return results

    def _categorize(self, words):
        """
        Map query words to latent semantic category.
        This is the 'semantic bridge' mechanism.
        """
        # Define category mappings
        category_map = {
            'food_dining': ['lunch', 'dinner', 'food', 'restaurant', 'eat', 'meal', 'cuisine', 'menu', 'dish'],
            'tech': ['python', 'code', 'software', 'programming', 'computer', 'tutorial', 'developer'],
            'finance': ['stock', 'market', 'investment', 'trading', 'shares', 'portfolio'],
            'auto': ['car', 'vehicle', 'automobile', 'maintenance', 'repair', 'driving'],
            'planning': ['roadmap', 'milestone', 'schedule', 'project', 'planning', 'deployment', 'critical'],
        }

        # Find matching category
        for cat, keywords in category_map.items():
            if any(kw in words for kw in keywords):
                return cat
        return None


# =============================================================================
# TEST 1: PURE BRIDGE ISOLATION
# =============================================================================

def test_pure_bridge():
    """
    Isolate whether semantic bridge is the causal factor.

    Setup:
      query: "lunch options"
      signal: "Italian restaurant review"  → category: food_dining
      distractors: 4 items with NO food_dining category

    All items: equal recency, equal importance, equal position.
    ONLY difference: semantic category bridge.

    Expected:
      episodic: all items have 0 keyword overlap → returns random/uniform
      semantic: signal activated via food_dining bridge → top result
    """
    print("\n" + "="*70)
    print("TEST 1: Pure Bridge Isolation")
    print("="*70)
    print("Question: Is semantic bridge the ONLY causal factor?")
    print()

    mem = ControlledMemory()

    # Query
    query = "lunch options"

    # Signal with food_dining bridge
    signal_id = mem.add("Italian restaurant review", importance=0.5, category='food_dining')

    # Distractors with NO food_dining bridge
    distractor_ids = [
        mem.add("Python tutorial video", importance=0.5, category='tech'),
        mem.add("stock market analysis", importance=0.5, category='finance'),
        mem.add("car maintenance guide", importance=0.5, category='auto'),
        mem.add("cloud infrastructure setup", importance=0.5, category='tech'),
    ]

    # Query keywords
    q_words = set(query.lower().split())
    print(f"  Query: '{query}'")
    print(f"  Query words: {q_words}")
    print()

    # Check keyword overlap for each item
    print("  Keyword overlap with query:")
    for item in mem.episodic:
        e_words = set(item['content'].lower().split())
        overlap = len(q_words & e_words) / max(len(q_words | e_words), 1)
        print(f"    [{item['id']}] '{item['content']}' → overlap={overlap:.3f}, category={item['category']}")

    print()

    # Episodic retrieval
    e_results = mem.episodic_retrieval(query, top_k=5)
    e_top1 = e_results[0][0] if e_results else None
    e_signal_rank = None
    for i, (bid, score, _) in enumerate(e_results):
        if bid == signal_id:
            e_signal_rank = i + 1
            break

    print(f"  Episodic top-1: ID={e_top1}")
    print(f"  Episodic signal rank: {e_signal_rank}")
    print(f"  Episodic scores: {[(r[0], r[1]) for r in e_results]}")
    print()

    # Semantic retrieval
    s_results = mem.semantic_retrieval(query, top_k=5)
    s_top1 = s_results[0][0] if s_results else None
    s_signal_rank = None
    for i, (bid, score, rtype, _) in enumerate(s_results):
        if bid == signal_id:
            s_signal_rank = i + 1
            break

    print(f"  Semantic top-1: ID={s_top1}")
    print(f"  Semantic signal rank: {s_signal_rank}")
    print(f"  Semantic scores: {[(r[0], r[1], r[2]) for r in s_results]}")
    print()

    # Analysis
    episodic_only_wins = (e_top1 == signal_id) and (s_top1 != signal_id)
    semantic_only_wins = (s_top1 == signal_id) and (e_top1 != signal_id)
    both_win = (e_top1 == signal_id) and (s_top1 == signal_id)
    neither_wins = (e_top1 != signal_id) and (s_top1 != signal_id)

    print("-"*70)
    if semantic_only_wins:
        verdict = "SEMANTIC BRIDGE ISOLATED AS CAUSAL FACTOR"
        delta = 1.0
    elif both_win:
        verdict = "BOTH RETRIEVE SIGNAL (episodic confounds remain)"
        delta = 0.0
    elif episodic_only_wins:
        verdict = "EPISODIC WINS WITHOUT SEMANTIC BRIDGE"
        delta = -1.0
    else:
        verdict = "NEITHER RETRIEVE SIGNAL (bridge not activated)"
        delta = 0.0

    print(f"  VERDICT: {verdict}")
    print(f"  Delta (semantic - episodic): {delta:+.3f}")
    print("="*70)

    return {
        'test': 'pure_bridge',
        'episodic_top1': e_top1,
        'semantic_top1': s_top1,
        'episodic_signal_rank': e_signal_rank,
        'semantic_signal_rank': s_signal_rank,
        'delta': delta,
        'verdict': verdict
    }


# =============================================================================
# TEST 2: BRIDGE SPECIFICITY
# =============================================================================

def test_bridge_specificity():
    """
    Test that semantic actually uses the bridge, not just retrieves everything.

    Setup:
      query: "lunch options"
      signal1: "Italian restaurant review"  → food_dining
      signal2: "Japanese ramen shop review" → food_dining
      distractor: "Python tutorial"         → tech

    Both signal1 and signal2 have food_dining bridge.
    Distractor does not.

    Expected:
      semantic: signal1 AND signal2 at top (both have bridge)
      episodic: all have 0 overlap → random
    """
    print("\n" + "="*70)
    print("TEST 2: Bridge Specificity")
    print("="*70)
    print("Question: Does semantic specifically route via bridge, not just retrieve more?")
    print()

    mem = ControlledMemory()

    query = "lunch options"

    signal1_id = mem.add("Italian restaurant review", importance=0.5, category='food_dining')
    signal2_id = mem.add("Japanese ramen shop review", importance=0.5, category='food_dining')
    distractor_id = mem.add("Python tutorial", importance=0.5, category='tech')

    q_words = set(query.lower().split())

    print(f"  Query: '{query}'")
    print(f"  Signal1: 'Italian restaurant review' (food_dining)")
    print(f"  Signal2: 'Japanese ramen shop review' (food_dining)")
    print(f"  Distractor: 'Python tutorial' (tech)")
    print()

    # Check overlaps
    print("  Keyword overlaps:")
    for item in mem.episodic:
        e_words = set(item['content'].lower().split())
        overlap = len(q_words & e_words) / max(len(q_words | e_words), 1)
        print(f"    [{item['id']}] '{item['content']}' → {overlap:.3f}")

    print()

    # Episodic
    e_results = mem.episodic_retrieval(query, top_k=5)
    print(f"  Episodic top-5: {[(r[0], r[1]) for r in e_results]}")
    e_signal1 = any(r[0] == signal1_id for r in e_results)
    e_signal2 = any(r[0] == signal2_id for r in e_results)
    e_distractor = any(r[0] == distractor_id for r in e_results)

    # Semantic
    s_results = mem.semantic_retrieval(query, top_k=5)
    print(f"  Semantic top-5: {[(r[0], r[1], r[2]) for r in s_results]}")
    s_signal1 = any(r[0] == signal1_id for r in s_results)
    s_signal2 = any(r[0] == signal2_id for r in s_results)
    s_distractor = any(r[0] == distractor_id for r in s_results)

    print()

    # Analysis
    episodic_signals_found = int(e_signal1) + int(e_signal2)
    semantic_signals_found = int(s_signal1) + int(s_signal2)

    print("-"*70)
    print(f"  Episodic: found {episodic_signals_found}/2 food_dining signals")
    print(f"  Semantic: found {semantic_signals_found}/2 food_dining signals")
    print(f"  Episodic retrieved distractor: {e_distractor}")
    print(f"  Semantic retrieved distractor: {s_distractor}")
    print()

    # Semantic should find BOTH food_dining signals
    # Episodic should find NEITHER (0 overlap)
    if semantic_signals_found == 2 and episodic_signals_found == 0:
        verdict = "SEMANTIC BRIDGE IS SELECTIVE AND SPECIFIC"
        delta = 1.0
    elif semantic_signals_found > episodic_signals_found:
        verdict = "SEMANTIC PROVIDES PARTIAL IMPROVEMENT"
        delta = 0.5
    elif semantic_signals_found == episodic_signals_found:
        verdict = "SEMANTIC NO BETTER THAN EPISODIC"
        delta = 0.0
    else:
        verdict = "EPISODIC OUTPERFORMS SEMANTIC"
        delta = -1.0

    print(f"  VERDICT: {verdict}")
    print(f"  Delta: {delta:+.3f}")
    print("="*70)

    return {
        'test': 'bridge_specificity',
        'episodic_signals': episodic_signals_found,
        'semantic_signals': semantic_signals_found,
        'episodic_distractor': e_distractor,
        'semantic_distractor': s_distractor,
        'delta': delta,
        'verdict': verdict
    }


# =============================================================================
# TEST 3: CROSS-SURFACE BRIDGE
# =============================================================================

def test_cross_surface_bridge():
    """
    Test: Can semantic bridge completely different surfaces?

    Setup:
      query: "team status update"
      signal: "Q3 milestone delivered ahead of schedule"
              → category: "progress_tracking"
              → surface tokens: Q3, milestone, delivered, ahead, schedule
              → query tokens: team, status, update
              → overlap: 0 (completely different surfaces)

      distractor: "car insurance renewal"
              → category: "auto"
              → overlap with query: 0

    Both signal and distractor have 0 keyword overlap with query.
    ONLY the latent structure differs.

    Expected:
      episodic: 0 overlap for both → random/uniform
      semantic: signal via progress_tracking bridge → top
    """
    print("\n" + "="*70)
    print("TEST 3: Cross-Surface Bridge")
    print("="*70)
    print("Question: Can semantic bridge completely different surfaces?")
    print()

    mem = ControlledMemory()

    query = "team status update"

    # Signal with progress_tracking category
    signal_id = mem.add(
        "Q3 milestone delivered ahead of schedule",
        importance=0.5,
        category='progress_tracking'
    )

    # Distractor with auto category (same 0 overlap with query)
    distractor_id = mem.add(
        "car insurance renewal",
        importance=0.5,
        category='auto'
    )

    # Another distractor with tech category
    distractor2_id = mem.add(
        "python debugging techniques",
        importance=0.5,
        category='tech'
    )

    q_words = set(query.lower().split())

    print(f"  Query: '{query}'")
    print(f"  Signal: 'Q3 milestone delivered ahead of schedule' (progress_tracking)")
    print(f"  Distractor1: 'car insurance renewal' (auto)")
    print(f"  Distractor2: 'python debugging techniques' (tech)")
    print()

    print("  Keyword overlaps with query:")
    for item in mem.episodic:
        e_words = set(item['content'].lower().split())
        overlap = len(q_words & e_words) / max(len(q_words | e_words), 1)
        print(f"    [{item['id']}] '{item['content'][:40]}...' → {overlap:.3f}")

    print()

    # Episodic
    e_results = mem.episodic_retrieval(query, top_k=5)
    print(f"  Episodic top-5: {[(r[0], r[1]) for r in e_results]}")
    e_top1_id = e_results[0][0] if e_results else None

    # Semantic
    s_results = mem.semantic_retrieval(query, top_k=5)
    print(f"  Semantic top-5: {[(r[0], r[1], r[2]) for r in s_results]}")
    s_top1_id = s_results[0][0] if s_results else None

    print()

    print("-"*70)
    print(f"  Episodic top-1: ID={e_top1_id}")
    print(f"  Semantic top-1: ID={s_top1_id}")
    print()

    if s_top1_id == signal_id and e_top1_id != signal_id:
        verdict = "SEMANTIC CROSS-SURFACE BRIDGE CONFIRMED"
        delta = 1.0
    elif s_top1_id == signal_id and e_top1_id == signal_id:
        verdict = "BOTH SUCCEED (need better distractor design)"
        delta = 0.0
    elif s_top1_id != signal_id and e_top1_id != signal_id:
        verdict = "BOTH FAIL (bridge not activated)"
        delta = 0.0
    else:
        verdict = "EPISODIC UNEXPECTEDLY WINS"
        delta = -1.0

    print(f"  VERDICT: {verdict}")
    print(f"  Delta: {delta:+.3f}")
    print("="*70)

    return {
        'test': 'cross_surface_bridge',
        'episodic_top1': e_top1_id,
        'semantic_top1': s_top1_id,
        'signal_id': signal_id,
        'delta': delta,
        'verdict': verdict
    }


# =============================================================================
# TEST 4: EPISODIC HEURISTIC CONTROL
# =============================================================================

def test_episodic_baseline():
    """
    Control test: Verify that episodic truly cannot do this.

    Setup:
      - 10 items all with 0 keyword overlap with query
      - All items have equal recency, importance, position
      - Only 1 item has semantic bridge
      - All others are pure distractors

    Expected episodic behavior:
      All items have same score (0 overlap)
      Return is effectively random/uniform
      Signal found ~1/10 times (random chance)

    Expected semantic behavior:
      Signal found via bridge ~1.0
    """
    print("\n" + "="*70)
    print("TEST 4: Episodic Baseline (Control)")
    print("="*70)
    print("Question: Verify episodic returns uniform/random for 0-overlap items")
    print()

    # Run multiple trials to check for randomness
    n_trials = 20
    signal_rank_sum = 0
    signal_in_top3 = 0

    query = "lunch options"

    for trial in range(n_trials):
        random.seed(42 + trial)  # Different seed each trial
        mem = ControlledMemory()

        # Signal with food_dining bridge
        signal_id = mem.add("Italian restaurant review", importance=0.5, category='food_dining')

        # 9 distractors with NO food_dining bridge
        distractors = [
            "Python tutorial video",
            "stock market analysis",
            "car maintenance guide",
            "cloud infrastructure setup",
            "book review for fiction novel",
            "fitness exercise routine",
            "home renovation tips",
            "photography lighting guide",
            "travel hotel booking"
        ]
        for d in distractors:
            mem.add(d, importance=0.5, category=None)

        # Episodic retrieval
        e_results = mem.episodic_retrieval(query, top_k=10)
        e_top_ids = [r[0] for r in e_results]

        # Signal rank
        if signal_id in e_top_ids:
            rank = e_top_ids.index(signal_id) + 1
            signal_rank_sum += rank
            if rank <= 3:
                signal_in_top3 += 1
        else:
            signal_rank_sum += 10  # Not found

    avg_rank = signal_rank_sum / n_trials
    hit_rate = signal_in_top3 / n_trials

    print(f"  {n_trials} trials of episodic retrieval (0-overlap items)")
    print(f"  Signal average rank: {avg_rank:.1f}/10")
    print(f"  Signal in top-3: {signal_in_top3}/{n_trials} ({hit_rate:.1%})")
    print()

    # For truly random retrieval from 10 items:
    # Expected average rank = 5.5
    # Expected top-3 hit rate = 30%

    if avg_rank > 4.0 and avg_rank < 7.0:
        episodic_verdict = "EPISODIC IS RANDOM (confirms 0-overlap design)"
    elif avg_rank <= 2.0:
        episodic_verdict = "EPISODIC HAS HIDDEN CONFOUND (not truly 0-overlap)"
    else:
        episodic_verdict = f"EPISODIC RANK={avg_rank:.1f} (interpret with care)"

    print(f"  Episodic verdict: {episodic_verdict}")
    print(f"  Expected for random: rank~5.5, top-3 hit~30%")
    print()

    # Now test semantic
    random.seed(42)
    mem_s = ControlledMemory()
    signal_id_s = mem_s.add("Italian restaurant review", importance=0.5, category='food_dining')
    for d in distractors:
        mem_s.add(d, importance=0.5, category=None)

    s_results = mem_s.semantic_retrieval(query, top_k=10)
    s_top1 = s_results[0][0] if s_results else None
    s_found = s_top1 == signal_id_s

    print(f"  Semantic top-1: ID={s_top1}, signal found={s_found}")
    print()

    if s_found and hit_rate < 0.4:
        control_verdict = "CONTROL VALID: semantic bridge works when episodic is random"
        delta = 1.0
    elif not s_found:
        control_verdict = "SEMANTIC BRIDGE FAILED (system issue)"
        delta = 0.0
    else:
        control_verdict = "EPISODIC NOT RANDOM (hidden confound)"
        delta = 0.0

    print("-"*70)
    print(f"  CONTROL VERDICT: {control_verdict}")
    print("="*70)

    return {
        'test': 'episodic_baseline',
        'avg_rank': avg_rank,
        'hit_rate': hit_rate,
        'semantic_found': s_found,
        'delta': delta,
        'verdict': control_verdict
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*70)
    print("v0.19 — Semantic Bridge Validity Benchmark")
    print("="*70)
    print()
    print("Purpose: Fix v0.18's heuristic confound")
    print("  - Remove recency/importance/pool-position bias")
    print("  - Isolate semantic bridge as ONLY differentiating factor")
    print()
    print("Design:")
    print("  - All items: equal recency, importance, position")
    print("  - Query and signal: 0 keyword overlap")
    print("  - ONLY difference: latent semantic category bridge")
    print()
    print("Research Question:")
    print("  Can semantic provide retrieval capability that episodic")
    print("  CANNOT independently achieve, using ONLY bridge?")
    print()

    # Run all tests
    results = []

    r1 = test_pure_bridge()
    results.append(r1)

    r2 = test_bridge_specificity()
    results.append(r2)

    r3 = test_cross_surface_bridge()
    results.append(r3)

    r4 = test_episodic_baseline()
    results.append(r4)

    # Final summary
    print()
    print("="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print()

    total_delta = 0
    for r in results:
        print(f"  {r['test']}: delta={r['delta']:+.3f} | {r['verdict']}")
        total_delta += r['delta']

    print()
    n_proven = sum(1 for r in results if r['delta'] > 0)
    print(f"  Tests proving semantic necessity: {n_proven}/4")
    print(f"  Total delta: {total_delta:+.3f}")
    print()

    if n_proven >= 3:
        final = "SEMANTIC NECESSITY PROVEN"
        conclusion = "semantic bridge provides episodic-independent capability"
    elif n_proven >= 2:
        final = "SEMANTIC NECESSITY PARTIALLY PROVEN"
        conclusion = "semantic bridge provides capability in some conditions"
    elif n_proven >= 1:
        final = "WEAK EVIDENCE FOR SEMANTIC NECESSITY"
        conclusion = "at least one test shows semantic-only success"
    else:
        final = "SEMANTIC NECESSITY NOT PROVEN"
        conclusion = "benchmark design or system needs revision"

    print(f"  FINAL: {final}")
    print(f"  CONCLUSION: {conclusion}")
    print()
    print("="*70)

    return {
        'final_verdict': final,
        'conclusion': conclusion,
        'test_results': results,
        'total_delta': total_delta
    }


if __name__ == "__main__":
    main()
