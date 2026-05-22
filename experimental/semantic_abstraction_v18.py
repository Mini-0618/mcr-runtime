#!/usr/bin/env python3
"""
v0.18 — Semantic Abstraction Benchmark
=======================================

Research Question: Does semantic form true Level-2 abstraction
                (invariant representation) beyond Level-1 routing?

Three-Layer Framework:
  Level 0: Keyword Retrieval (BM25-like, surface token overlap)
  Level 1: Routing Prior (cluster bias, topic routing, entropy reduction)
  Level 2: Abstraction / Invariant Representation (cross-surface structure,
           latent pattern extraction, schema generalization)

v0.17 Result: Level 1 confirmed, Level 2 NOT proven
  - episodic still wins via recency + importance + keyword overlap
  - benchmark tasks didn't push episodic to failure regime

v0.18 Design Principle:
  Signal MUST satisfy ALL of:
    1. NO keyword match with query
    2. NO recency advantage
    3. NO importance advantage
    4. COMPLETELY different surface form
    5. SAME underlying latent structure

  Only then can semantic's abstraction capability be tested.

Task A: Structure Equivalence
  - phase1/2/3: different surface, same structure
  - episodic: token overlap ≈ 0, recency失效
  - semantic: if invariant forms, cross-surface activation

Task B: Adversarial Distractor Flood
  - signal: oldest + lowest importance + no keyword advantage
  - distractors: newest + highest importance + high surface overlap
  - forces episodic heuristic collapse

Task C: Cross-Episode Compression
  - 5 episodic: different wording/context/token, same latent structure
  - tests whether semantic can merge/compress/generalize
"""

import random
import math
import json
from collections import defaultdict

random.seed(42)

# =============================================================================
# CORE MEMORY SYSTEM (minimal Layer 0-2 simulation)
# =============================================================================

class MiniMemory:
    """Simplified memory system with Layer 0 (episodic) and Layer 1 (semantic)."""

    def __init__(self):
        self.episodic = []  # list of (content, timestamp, importance, embedding)
        self.semantic = {}   # cluster_id -> schema

    def add_episodic(self, content, importance=0.5):
        ts = len(self.episodic)
        emb = self._embed(content)
        self.episodic.append((content, ts, importance, emb))

    def add_semantic(self, cluster_id, schema_content, activation=0.0):
        """Add a semantic schema (Level 2 representation)."""
        self.semantic[cluster_id] = {
            'content': schema_content,
            'activation': activation,
            'episode_refs': []
        }

    def _embed(self, text):
        """Shallow word-based embedding (Level 0)."""
        words = set(text.lower().split())
        return words

    def episodic_retrieval(self, query, top_k=5):
        """Level 0: Pure keyword/recency retrieval."""
        q_emb = self._embed(query)
        scores = []
        for i, (content, ts, importance, emb) in enumerate(self.episodic):
            # Keyword overlap
            overlap = len(q_emb & emb) / max(len(q_emb | emb), 1)
            # Recency score (normalized)
            recency = ts / max(len(self.episodic), 1)
            # Combined score (episodic heuristic)
            score = 0.4 * overlap + 0.3 * recency + 0.3 * importance
            scores.append((i, score))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    def semantic_retrieval(self, query, top_k=5):
        """Level 1+2: Routing + Abstraction retrieval."""
        q_emb = self._embed(query)
        results = []

        # Level 1: Check semantic schemas (routing layer)
        for cid, sch in self.semantic.items():
            s_emb = self._embed(sch['content'])
            overlap = len(q_emb & s_emb) / max(len(q_emb | s_emb), 1)
            score = sch['activation'] * 0.5 + overlap * 0.5
            results.append((cid, 'semantic', score))

        # Level 0: Also check episodic (for comparison)
        e_scores = self.episodic_retrieval(query, top_k)
        for i, score in e_scores:
            results.append((i, 'episodic', score))

        results.sort(key=lambda x: -x[2])
        return results[:top_k]

    def route_via_semantic(self, query):
        """Level 1: Semantic routing (entropy reduction)."""
        q_emb = self._embed(query)

        # Check if any semantic schema provides routing bias
        schema_activations = []
        for cid, sch in self.semantic.items():
            s_emb = self._embed(sch['content'])
            overlap = len(q_emb & s_emb)
            if overlap > 0:
                schema_activations.append((cid, overlap))

        if not schema_activations:
            return None, 0.0

        # Route to highest-matching schema
        best_schema = max(schema_activations, key=lambda x: x[1])
        return best_schema[0], best_schema[1]


# =============================================================================
# LEVEL 0 ONLY (episodic without semantic routing)
# =============================================================================

class EpisodicOnlyMemory(MiniMemory):
    """Memory system with ONLY Level 0 (no semantic routing)."""

    def retrieval(self, query, top_k=5):
        """Pure episodic retrieval - no semantic influence."""
        return self.episodic_retrieval(query, top_k)


# =============================================================================
# LEVEL 1+2 (full semantic system)
# =============================================================================

class FullSemanticMemory(MiniMemory):
    """Memory system with Level 1 (routing) + Level 2 (abstraction)."""

    def __init__(self):
        super().__init__()
        self.abstract_schemas = {}  # Level 2: invariant representations

    def form_schema(self, episodes, latent_structure, schema_id):
        """
        Attempt to form a Level 2 abstraction from multiple episodes.
        This is the CRITICAL test: can semantic merge surface-different
        episodes into invariant representation?
        """
        # Check if episodes share latent structure
        if latent_structure:
            # Form abstraction
            self.abstract_schemas[schema_id] = {
                'latent': latent_structure,
                'episodes': episodes,
                'activation': 0.5
            }
            # Also add as semantic routing node
            self.add_semantic(
                f"schema_{schema_id}",
                latent_structure,
                activation=0.5
            )
            return True
        return False

    def retrieve_with_abstraction(self, query, top_k=5):
        """
        Level 2 retrieval: Check if query matches abstract schemas
        even when surface tokens don't overlap.
        """
        q_emb = self._embed(query)
        results = []

        # Check Level 2 abstractions
        for sid, asc in self.abstract_schemas.items():
            # Abstract match: check if query relates to latent structure
            latent_emb = self._embed(asc['latent'])
            # Semantic equivalence (broader match)
            if q_emb & latent_emb:
                # Partial match counts for abstraction
                match_ratio = len(q_emb & latent_emb) / max(len(q_emb | latent_emb), 1)
                score = asc['activation'] * match_ratio
                results.append((sid, 'abstraction', score))

        # Also run Level 0 retrieval for comparison
        e_scores = self.episodic_retrieval(query, top_k)
        for i, score in e_scores:
            results.append((i, 'episodic', score))

        results.sort(key=lambda x: -x[2])
        return results


# =============================================================================
# TASK A: Structure Equivalence
# =============================================================================

def run_task_a():
    """
    Test: Can semantic detect invariant structure across different surfaces?

    Design:
      phase1: "roadmap milestone dependency"
      phase2: "deployment sequencing bottleneck"
      phase3: "schedule critical path constraint"

    Underlying structure: "ordered planning constraint"

    Episodic failure condition:
      - Token overlap between phases ≈ 0
      - Recency: phase1 oldest, phase3 newest (but query targets structure, not recency)
      - Importance: all equal
      - Query: "planning workflow optimization"

    Semantic success condition:
      - If invariant "ordered planning constraint" schema formed
      - Should activate across all three phases
    """
    print("\n" + "="*70)
    print("TASK A: Structure Equivalence")
    print("="*70)
    print("Question: Can semantic detect same structure across different surfaces?")
    print()

    results = {}

    # ----- Episodic Only -----
    mem_e = EpisodicOnlyMemory()

    # phase1: "roadmap milestone dependency"
    mem_e.add_episodic("roadmap milestone dependency", importance=0.5)
    # phase2: "deployment sequencing bottleneck"
    mem_e.add_episodic("deployment sequencing bottleneck", importance=0.5)
    # phase3: "schedule critical path constraint"
    mem_e.add_episodic("schedule critical path constraint", importance=0.5)

    query = "planning workflow optimization"

    # Check token overlap for each
    q_emb = mem_e._embed(query)
    p1_emb = mem_e._embed("roadmap milestone dependency")
    p2_emb = mem_e._embed("deployment sequencing bottleneck")
    p3_emb = mem_e._embed("schedule critical path constraint")

    p1_overlap = len(q_emb & p1_emb) / max(len(q_emb | p1_emb), 1)
    p2_overlap = len(q_emb & p2_emb) / max(len(q_emb | p2_emb), 1)
    p3_overlap = len(q_emb & p3_emb) / max(len(q_emb | p3_emb), 1)

    # Retrieval result
    retrieved = mem_e.retrieval(query, top_k=3)

    episodic_signal = 0.0
    if retrieved:
        # Check if any of the 3 phases appear in top results
        retrieved_ids = [r[0] for r in retrieved]
        if 0 in retrieved_ids or 1 in retrieved_ids or 2 in retrieved_ids:
            episodic_signal = 1.0

    results['episodic_only'] = {
        'p1_overlap': p1_overlap,
        'p2_overlap': p2_overlap,
        'p3_overlap': p3_overlap,
        'retrieved_ids': [r[0] for r in retrieved],
        'signal_detected': episodic_signal
    }

    print(f"  Query: '{query}'")
    print(f"  phase1 overlap: {p1_overlap:.3f}")
    print(f"  phase2 overlap: {p2_overlap:.3f}")
    print(f"  phase3 overlap: {p3_overlap:.3f}")
    print(f"  Retrieved IDs: {results['episodic_only']['retrieved_ids']}")
    print(f"  Signal detected (episodic): {episodic_signal}")
    print()

    # ----- Full Semantic (with schema formation) -----
    mem_s = FullSemanticMemory()

    # Add the three phases
    mem_s.add_episodic("roadmap milestone dependency", importance=0.5)
    mem_s.add_episodic("deployment sequencing bottleneck", importance=0.5)
    mem_s.add_episodic("schedule critical path constraint", importance=0.5)

    # CRITICAL: Form invariant schema from all three phases
    # This is the Level 2 abstraction attempt
    schema_formed = mem_s.form_schema(
        episodes=[0, 1, 2],
        latent_structure="ordered planning constraint",
        schema_id="planning_constraint"
    )

    # Query: does abstraction help?
    q_emb_s = mem_s._embed(query)
    retrieved_s = mem_s.retrieve_with_abstraction(query, top_k=5)

    # Check if schema appears in results
    semantic_signal = 0.0
    if retrieved_s:
        result_types = [r[1] for r in retrieved_s]
        if 'abstraction' in result_types:
            semantic_signal = 1.0
        # Also check if episodic found anything
        retrieved_ids_s = [r[0] for r in retrieved_s if r[1] == 'episodic']
        if 0 in retrieved_ids_s or 1 in retrieved_ids_s or 2 in retrieved_ids_s:
            semantic_signal = 1.0  # episodic also succeeded

    results['semantic_full'] = {
        'schema_formed': schema_formed,
        'retrieved': [(r[0], r[1], r[2]) for r in retrieved_s],
        'signal_detected': semantic_signal
    }

    print(f"  Schema formed: {schema_formed}")
    print(f"  Retrieved (semantic): {results['semantic_full']['retrieved']}")
    print(f"  Signal detected (semantic): {semantic_signal}")
    print()

    # ----- Analysis -----
    delta = semantic_signal - episodic_signal

    print("-" * 70)
    print(f"  Episodic signal: {episodic_signal:.3f}")
    print(f"  Semantic signal:  {semantic_signal:.3f}")
    print(f"  Delta:            {delta:+.3f}")
    print()

    if delta > 0:
        verdict = "SEMANTIC PROVIDES INDEPENDENT CAPABILITY"
    elif delta == 0 and semantic_signal == 0:
        verdict = "BOTH FAIL — structure abstraction needed"
    else:
        verdict = "EPISODIC EQUALS SEMANTIC"

    print(f"  VERDICT: {verdict}")
    print("=" * 70)

    return results, delta


# =============================================================================
# TASK B: Adversarial Distractor Flood
# =============================================================================

def run_task_b():
    """
    Test: Can semantic recover signal buried under adversarial distractor flood?

    Design:
      Signal (tick 50):
        - OLDEST (recency = 0)
        - LOWEST importance (0.1)
        - Keywords: unique but not shared with query
        - Content: "alpha critical resource"

      Distractor Flood (tick 100-1000):
        - 1000 items
        - NEWEST (high recency)
        - HIGHEST importance (0.9)
        - HIGH surface overlap with query

      Query: "beta project status update"

    Episodic failure condition:
      - Recency: all distractors >> signal
      - Importance: all distractors >> signal
      - Keyword: query overlaps with distractors, NOT with signal

    Semantic success condition:
      - If semantic forms "critical resource" schema
      - Should activate signal even without recency/importance
    """
    print("\n" + "="*70)
    print("TASK B: Adversarial Distractor Flood")
    print("="*70)
    print("Question: Can semantic recover old/weak signal under distractor flood?")
    print()

    results = {}

    # ----- Episodic Only -----
    mem_e = EpisodicOnlyMemory()

    # Signal at tick 50 (oldest, lowest importance)
    mem_e.add_episodic("alpha critical resource", importance=0.1)

    # Distractor flood (1000 items, newest, highest importance)
    query_keywords = ["beta", "project", "status", "update"]
    for i in range(1000):
        # Each distractor has high overlap with query
        distractor = f"beta project {query_keywords[i % 4]} {i}"
        mem_e.add_episodic(distractor, importance=0.9)

    # Query
    query = "beta project status update"
    retrieved = mem_e.retrieval(query, top_k=10)

    # Check: is signal (id=0) in top-10?
    episodic_signal = 0.0
    if retrieved:
        retrieved_ids = [r[0] for r in retrieved]
        if 0 in retrieved_ids:
            episodic_signal = 1.0

    results['episodic_only'] = {
        'signal_id': 0,
        'retrieved_ids': [r[0] for r in retrieved[:5]],
        'signal_in_top10': episodic_signal
    }

    print(f"  Signal: 'alpha critical resource' (oldest, imp=0.1)")
    print(f"  Distractors: 1000 items (newest, imp=0.9)")
    print(f"  Query: '{query}'")
    print(f"  Signal in top-10 (episodic): {episodic_signal}")
    print(f"  Retrieved IDs: {results['episodic_only']['retrieved_ids']}")
    print()

    # ----- Full Semantic -----
    mem_s = FullSemanticMemory()

    # Signal
    mem_s.add_episodic("alpha critical resource", importance=0.1)

    # Distractor flood
    for i in range(1000):
        distractor = f"beta project {query_keywords[i % 4]} {i}"
        mem_s.add_episodic(distractor, importance=0.9)

    # Try to form schema around "critical resource" structure
    # This is the Level 2 abstraction attempt
    schema_formed = mem_s.form_schema(
        episodes=[0],  # only the signal
        latent_structure="critical resource allocation",
        schema_id="critical_res"
    )

    # Retrieval with abstraction
    retrieved_s = mem_s.retrieve_with_abstraction(query, top_k=10)

    semantic_signal = 0.0
    if retrieved_s:
        retrieved_types = [(r[0], r[1]) for r in retrieved_s]
        # Check if abstraction retrieved the signal
        for r_id, r_type in retrieved_types:
            if r_type == 'abstraction' and r_id == 'critical_res':
                semantic_signal = 1.0
        # Or if episodic found it (but with heavy penalty)
        if 0 in [r[0] for r in retrieved_s if r[1] == 'episodic']:
            # Episodic also found it — semantic didn't help specifically
            pass

    results['semantic_full'] = {
        'schema_formed': schema_formed,
        'retrieved': [(r[0], r[1], r[2]) for r in retrieved_s[:5]],
        'signal_via_abstraction': semantic_signal
    }

    print(f"  Schema formed: {schema_formed}")
    print(f"  Retrieved (semantic): {results['semantic_full']['retrieved']}")
    print(f"  Signal via abstraction: {semantic_signal}")
    print()

    # ----- Analysis -----
    delta = semantic_signal - episodic_signal

    print("-" * 70)
    print(f"  Episodic signal: {episodic_signal:.3f}")
    print(f"  Semantic signal:  {semantic_signal:.3f}")
    print(f"  Delta:            {delta:+.3f}")
    print()

    if delta > 0:
        verdict = "SEMANTIC RECOVERS BURIED SIGNAL"
    elif episodic_signal == 0 and semantic_signal == 0:
        verdict = "BOTH FAIL — need stronger abstraction"
    else:
        verdict = "EPISODIC EQUALS SEMANTIC"

    print(f"  VERDICT: {verdict}")
    print("=" * 70)

    return results, delta


# =============================================================================
# TASK C: Cross-Episode Compression
# =============================================================================

def run_task_c():
    """
    Test: Can semantic merge different-surface episodes into unified schema?

    Design:
      5 episodic entries (different surface, same latent):
        1. "Q1 project on track"
        2. "phase2 ahead of schedule"
        3. "milestone3 completed"
        4. "iteration4 delivered"
        5. "sprint5 shipped"

      Query: "progress update"

      All surface tokens different from "progress update"
      But all share latent structure: "project progress reporting"

    Episodic failure condition:
      - No episodic has keyword overlap with "progress update"
      - No episodic has recency advantage
      - No episodic has importance advantage

    Semantic success condition:
      - If "progress_reporting" schema formed
      - Should activate all 5 dispersely-related episodics
    """
    print("\n" + "="*70)
    print("TASK C: Cross-Episode Compression")
    print("="*70)
    print("Question: Can semantic merge different-surface episodes into unified schema?")
    print()

    results = {}

    # ----- Episodic Only -----
    mem_e = EpisodicOnlyMemory()

    episodes = [
        "Q1 project on track",
        "phase2 ahead of schedule",
        "milestone3 completed",
        "iteration4 delivered",
        "sprint5 shipped"
    ]

    for e in episodes:
        mem_e.add_episodic(e, importance=0.5)

    query = "progress update"
    retrieved = mem_e.retrieval(query, top_k=5)

    # Check: how many of the 5 episodes found?
    episodic_found = 0
    if retrieved:
        retrieved_ids = [r[0] for r in retrieved]
        episodic_found = sum(1 for i in range(5) if i in retrieved_ids)

    episodic_signal = episodic_found / 5.0  # ratio

    results['episodic_only'] = {
        'episodes_found': episodic_found,
        'retrieved_ids': [r[0] for r in retrieved],
        'signal_ratio': episodic_signal
    }

    print(f"  Episodes: {episodes}")
    print(f"  Query: '{query}'")
    print(f"  Episodes found (episodic): {episodic_found}/5")
    print(f"  Retrieved IDs: {results['episodic_only']['retrieved_ids']}")
    print()

    # ----- Full Semantic -----
    mem_s = FullSemanticMemory()

    for e in episodes:
        mem_s.add_episodic(e, importance=0.5)

    # CRITICAL: Form unified schema from all 5 episodes
    # Level 2 abstraction: compress different surfaces into invariant
    schema_formed = mem_s.form_schema(
        episodes=[0, 1, 2, 3, 4],
        latent_structure="project progress reporting",
        schema_id="progress_report"
    )

    # Retrieval with abstraction
    retrieved_s = mem_s.retrieve_with_abstraction(query, top_k=10)

    # Check abstraction activation
    abstraction_found = 0
    episodic_found_s = 0
    if retrieved_s:
        for r_id, r_type, r_score in retrieved_s:
            if r_type == 'abstraction' and r_id == 'progress_report':
                abstraction_found = 1
            if r_type == 'episodic' and r_id in range(5):
                episodic_found_s += 1

    semantic_signal = abstraction_found  # abstraction is the key test

    results['semantic_full'] = {
        'schema_formed': schema_formed,
        'abstraction_found': abstraction_found,
        'episodic_found': episodic_found_s,
        'retrieved': [(r[0], r[1], r[2]) for r in retrieved_s[:5]],
        'signal': semantic_signal
    }

    print(f"  Schema formed: {schema_formed}")
    print(f"  Abstraction activated: {abstraction_found}")
    print(f"  Episodic found (semantic): {episodic_found_s}/5")
    print(f"  Retrieved: {results['semantic_full']['retrieved']}")
    print()

    # ----- Analysis -----
    delta = semantic_signal - episodic_signal

    print("-" * 70)
    print(f"  Episodic recall ratio: {episodic_signal:.3f}")
    print(f"  Semantic abstraction:   {semantic_signal:.3f}")
    print(f"  Delta:                  {delta:+.3f}")
    print()

    if delta > 0:
        verdict = "SEMANTIC COMPRESSES CROSS-EPISODE STRUCTURE"
    elif episodic_signal == 0 and semantic_signal == 0:
        verdict = "BOTH FAIL — no abstraction mechanism active"
    else:
        verdict = "EPISODIC EQUALS SEMANTIC"

    print(f"  VERDICT: {verdict}")
    print("=" * 70)

    return results, delta


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*70)
    print("v0.18 — Semantic Abstraction Benchmark")
    print("="*70)
    print()
    print("Research Question: Does semantic form Level-2 abstraction")
    print("                   beyond Level-1 routing stabilization?")
    print()
    print("Three-Layer Framework:")
    print("  Level 0: Keyword Retrieval (surface token overlap)")
    print("  Level 1: Routing Prior (cluster bias, topic routing)")
    print("  Level 2: Abstraction (invariant representation)")
    print()
    print("Design Principle:")
    print("  Signal MUST have:")
    print("    1. NO keyword match with query")
    print("    2. NO recency advantage")
    print("    3. NO importance advantage")
    print("    4. COMPLETELY different surface form")
    print("    5. SAME underlying latent structure")
    print()

    results_a, delta_a = run_task_a()
    results_b, delta_b = run_task_b()
    results_c, delta_c = run_task_c()

    # ----- Final Verdict -----
    print()
    print("="*70)
    print("SEMANTIC ABSTRACTION VERDICT")
    print("="*70)
    print()
    print(f"Task A (Structure Equivalence):       delta = {delta_a:+.3f}")
    print(f"Task B (Adversarial Distractor):    delta = {delta_b:+.3f}")
    print(f"Task C (Cross-Episode Compression): delta = {delta_c:+.3f}")
    print()

    tasks_proven = sum(1 for d in [delta_a, delta_b, delta_c] if d > 0)

    if tasks_proven >= 2:
        final_verdict = "LEVEL-2 ABSTRACTION OBSERVED"
        conclusion = "semantic forms invariant representations beyond routing"
    elif tasks_proven == 1:
        final_verdict = "PARTIAL ABSTRACTION EVIDENCE"
        conclusion = "one task shows semantic-only capability"
    else:
        final_verdict = "LEVEL-2 ABSTRACTION NOT PROVEN"
        conclusion = "semantic remains routing-layer system"

    print(f"Tasks with semantic-only success: {tasks_proven}/3")
    print()
    print(f"FINAL VERDICT: {final_verdict}")
    print(f"CONCLUSION: {conclusion}")
    print()
    print("="*70)

    return {
        'verdict': final_verdict,
        'conclusion': conclusion,
        'task_deltas': {'A': delta_a, 'B': delta_b, 'C': delta_c},
        'tasks_proven': tasks_proven
    }


if __name__ == "__main__":
    main()
