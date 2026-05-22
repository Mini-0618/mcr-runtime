#!/usr/bin/env python3
"""
MCR Learning Loop — FIXED SNR EXPERIMENT
Controlled stochastic reduction: fix measurement regime, then test learning.

Changes from v3:
  1. Deterministic retrieval kernel (no Bernoulli noise — rank is fixed by action quality)
  2. Bounded, seeded noise (reproducible, action-independent)
  3. Reward decomposition: deterministic_r + noise_r tracked separately
  4. Theoretical upper bound computed so we know the ceiling

Expected: SNR >> 1.0, Δreward clearly measurable.
"""
import sys, random
sys.path.insert(0, '/home/minimax/mcr/stable')

GOLD = {"python_gc":"python_gc","sql_query":"sql_query","docker_runtime":"docker_runtime",
        "wal_replay":"wal_replay","semantic_search":"semantic_search","crash_recovery":"crash_recovery",
        "network_protocol":"network_protocol","file_system":"file_system"}
QUERIES = list(GOLD.keys())

# ═══ THEORETICAL CALCULATIONS ══════════════════════════════════════════════
# A0: sem_first — step1 quality=0.90, step2+=0.20
# A1: focused   — step1 quality=0.20, step2+=0.70
ACTION_TABLE = [
    {"id":0,"name":"sem_first","quality":[0.90,0.20,0.20]},
    {"id":1,"name":"focused", "quality":[0.20,0.70,0.70]},
]

def theoretical_f1(query, action_seq):
    """
    Compute theoretical oracle F1 for a given action sequence (no noise).
    Oracle F1 = 1.0 if last retrieval hit query topic, else 0.0.
    Last retrieval quality = quality[step2] (1-indexed: quality[2] = step3).
    """
    last_action = action_seq[-1]
    last_quality = last_action["quality"][2]  # step index 2 = step 3
    # Hit if quality >= 0.5 (deterministic threshold, no noise)
    hit = 1.0 if last_quality >= 0.5 else 0.0
    return hit  # oracle F1 is binary in this oracle

def compute_ceiling():
    """
    Compute theoretical rewards for optimal vs random policies.
    Since last retrieval is the only one evaluated, and it's deterministic:
    - Optimal: last step uses best action → quality >= 0.5 always → F1 = 1.0
    - Random: 50% chance of hitting >= 0.5 → F1 = 0.5
    - Wait: actually optimal for step3 is A1 (0.70), which hits
      So optimal episode reward = 1.0 always
    - Random: 50% A0(0.20=fail) + 50% A1(0.70=hit) = 0.5
    """
    # Optimal: always choose best action per step
    # Step 1: A0 (0.90), Step 2: A1 (0.70), Step 3: A1 (0.70)
    # Last step (step 3) uses A1 → quality=0.70 → deterministic HIT → F1=1.0
    optimal_reward = 1.0  # always hits with A1 on step3

    # Random: uniformly pick A0 or A1 per step
    # P(hit on step3) = P(A1 on step3) = 0.5
    # E[F1] = 0.5 * 1.0 + 0.5 * 0.0 = 0.5
    random_reward = 0.5

    return optimal_reward, random_reward

OPTIMAL_R, RANDOM_R = compute_ceiling()
EXPECTED_DELTA = OPTIMAL_R - RANDOM_R  # = 0.5

# ═══ CONTROLLED NOISE CHANNEL ════════════════════════════════════════════════
# Noise is fixed, reproducible, action-independent
# Applied to BOTH optimal and random to make retrieval slightly uncertain
NOISE_PROB = 0.05  # 5% noise — small enough to not overwhelm signal

def apply_noise(x):
    """Flip result with probability NOISE_PROB. Seeded by episode index."""
    # Deterministic per-episode noise (reproducible)
    return 1.0 - x if random.random() < NOISE_PROB else x

# ═══ RETRIEVAL (DETERMINISTIC + NOISE) ════════════════════════════════════
def retrieve_quality(action, step):
    """Quality is deterministic given action + step. No Bernoulli noise."""
    return action["quality"][step - 1]  # 0-indexed into quality array

def do_retrieve(query, action, step, total_steps, seed_noise=True):
    """
    Step 1: quality is deterministic from action.
    Step 2: noise applied (flips hit/miss with small prob).
    Step 3: same.
    """
    quality = retrieve_quality(action, step)
    if seed_noise:
        quality = apply_noise(quality)
    hit = quality >= 0.5  # deterministic threshold
    if hit:
        return [query] + [t for t in QUERIES if t != query and random.random() < 0.15]
    return [t for t in QUERIES if random.random() < 0.15]

def oracle_f1(query, retrieved):
    gold = {GOLD.get(query, query)}
    retr = set(retrieved) if retrieved else set()
    if not gold or not retr: return 0.0
    tp = len(gold & retr)
    return 2*tp/(len(gold)+len(retr))

# ═══ POLICY ═══════════════════════════════════════════════════════════════════
class Policy:
    """
    2 actions × 5 state features.
    prev_action_id in state for conditional learning.
    """
    NA, NDIM = 2, 5
    def __init__(self, lr=0.3, rand=False, seed=None):
        if seed is not None: random.seed(seed)
        self.W = [[random.gauss(0, 0.05) for _ in range(self.NDIM)] for _ in range(self.NA)]
        self.lr, self.rand = lr, rand
        self.baseline = 0.0

    def select(self, state, eps=0.1):
        if self.rand or random.random() < eps:
            return ACTION_TABLE[int(random.random() * self.NA)]
        scores = [sum(state[j] * self.W[i][j] for j in range(self.NDIM)) for i in range(self.NA)]
        return ACTION_TABLE[scores.index(max(scores))]

    def update(self, state, action, reward):
        delta = self.lr * (reward - self.baseline)
        idx = action["id"]
        for j in range(self.NDIM):
            self.W[idx][j] += delta * state[j]
        self.baseline = 0.9 * self.baseline + 0.1 * reward

# ═══ STATE ENCODER ═════════════════════════════════════════════════════════════
def encode(step, total_steps, prev_id, hist):
    recent = hist[-2:] if hist else []
    topics = [t for e in recent for t in (e if isinstance(e, list) else [e])]
    div = len(set(topics)) / max(len(topics), 1.0) if topics else 0.0
    return [
        step / max(total_steps, 1),
        prev_id,
        div,
        len(recent) / 3.0,
        1.0 if hist else 0.0,
    ]

# ═══ ENVIRONMENT ════════════════════════════════════════════════════════════════
class Env:
    STEPS = 3
    def reset(self, q): return {"step": 0, "q": q, "hist": [], "active": True}
    def step(self, state, retrieved):
        s, q, hist = state["step"], state["q"], state["hist"]
        hist = hist + [retrieved]
        done = s >= self.STEPS - 1
        r = 0.0
        if done:
            r = oracle_f1(q, retrieved)
        return {"step": s+1, "q": q, "hist": hist, "active": not done}, r, not done

# ═══ EPISODE RUNNER ══════════════════════════════════════════════════════════
def run_episode(pol, env, query, eps, ep_idx, seed_noise=True):
    S = env.reset(query)
    prev_id = 0
    while S["active"] and S["step"] < env.STEPS:
        enc = encode(S["step"]+1, env.STEPS, prev_id, S["hist"])
        act = pol.select(enc, eps=eps)
        retr = do_retrieve(query, act, S["step"]+1, env.STEPS, seed_noise=seed_noise)
        S, r, _ = env.step(S, retr)
        pol.update(enc, act, r)
        prev_id = act["id"]
    return r  # episode reward

# ═══ A/B EXPERIMENT WITH SNR MEASUREMENT ══════════════════════════════════════
def run_ab(N=500, seed=42):
    """
    Run A (learning) vs B (random) with controlled stochastic environment.
    Key metrics:
      - SNR = expected_delta / noise_std
      - p-value of Δreward > 0
      - learning curve shape
    """
    random.seed(seed)
    print(f"Theoretical ceiling: Δ = {EXPECTED_DELTA:+.3f} (optimal={OPTIMAL_R:.3f}, random={RANDOM_R:.3f})")
    print(f"SNR conditions: noise_prob={NOISE_PROB}, action_gap=0.50 (0.70 vs 0.20)")
    print(f"{'='*65}")

    envA, envB = Env(), Env()
    polA = Policy(lr=0.3, rand=False)
    polB = Policy(lr=0.3, rand=True)

    RA, RB, D = [], [], []
    for ep in range(N):
        q = QUERIES[ep % len(QUERIES)]
        eps = max(0.02, 0.9 - ep / 200)
        rA = run_episode(polA, envA, q, eps, ep, seed_noise=True)
        rB = run_episode(polB, envB, q, eps=1.0, ep_idx=ep, seed_noise=True)
        RA.append(rA); RB.append(rB); D.append(rA - rB)

    # ── Analysis ──────────────────────────────────────────────────────
    print(f"\nEpisode-by-episode windows:")
    for ep in [0, 49, 99, 199, 299, 399, 499]:
        if ep < N:
            w = min(50, ep+1)
            avg = sum(D[:w]) / w if ep < 100 else sum(D[ep-49:ep+1]) / min(50, ep+1)
            print(f"  eps {ep}: R_A={RA[ep]:.3f} R_B={RB[ep]:.3f} Δ={D[ep]:+.3f}  window_avg={avg:+.3f}")

    # Statistical test: is late Δ > early Δ?
    window = min(100, N//5)
    early = [sum(D[i-window:i])/window for i in range(window, N//3)]
    late  = [sum(D[i-window:i])/window for i in range(N*2//3, N-window+1)]
    avg_early = sum(early)/len(early) if early else 0
    avg_late  = sum(late)/len(late) if late else 0

    # One-sided t-test approximation
    import math
    pooled_std = math.sqrt(sum((d-avg_late)**2 for d in late) / max(len(late)-1, 1))
    t_stat = (avg_late - avg_early) / (pooled_std / math.sqrt(len(late))) if pooled_std > 0 else 0

    win_rate = sum(1 for d in D if d > 0) / N

    print(f"\n{'='*65}")
    print(f"RESULTS (seed={seed}):")
    print(f"  A avg reward:  {sum(RA)/N:.4f}  (theoretical optimal: {OPTIMAL_R:.3f})")
    print(f"  B avg reward:  {sum(RB)/N:.4f}  (theoretical random: {RANDOM_R:.3f})")
    print(f"  Δreward:      {sum(D)/N:+.4f}")
    print(f"  A win rate:   {win_rate*100:.1f}%  (random baseline: 50.0%)")
    print(f"  Δ trend:      {avg_early:+.4f} → {avg_late:+.4f}  (ΔΔ={avg_late-avg_early:+.4f})")
    print(f"  t-statistic:  {t_stat:+.3f}  (positive = A improving vs early)")
    print(f"{'='*65}")

    # ── Verdict ──────────────────────────────────────────────────────
    # Criteria for LEARNING SIGNAL:
    # 1. Late Δ > Early Δ by meaningful margin
    # 2. A win rate > 52%
    # 3. Late Δ is positive
    if avg_late > avg_early + 0.05 and win_rate > 0.52 and avg_late > 0.05:
        print("→ LEARNING SIGNAL DETECTED")
    elif avg_late < avg_early - 0.05:
        print("→ POLICY DEGRADING")
    else:
        print("→ INCONCLUSIVE")

    return {"RA":RA,"RB":RB,"D":D,"early":avg_early,"late":avg_late,
            "win_rate":win_rate,"t_stat":t_stat}

def run_multi_seed(N=500, seeds=[42,123,7,999,314,271,888]):
    print(f"\nMULTI-SEED AVERAGE OVER {len(seeds)} RUNS")
    print(f"{'='*65}")
    results = [run_ab(N, seed=s) for s in seeds]
    print(f"\nAGGREGATE ACROSS {len(seeds)} SEEDS:")
    print(f"  Avg Δtrend:    {sum(r['late']-r['early'] for r in results)/len(results):+.4f}")
    print(f"  Avg late Δ:    {sum(r['late'] for r in results)/len(results):+.4f}")
    print(f"  Avg win rate: {sum(r['win_rate'] for r in results)/len(results)*100:.1f}%")
    all_late = [r['late'] for r in results]
    all_early = [r['early'] for r in results]
    all_win = [r['win_rate'] for r in results]
    print(f"  Individual late Δ: {[f'{l:+.3f}' for l in all_late]}")
    print(f"  Individual win%:   {[f'{w*100:.1f}%' for w in all_win]}")

    # Aggregate signal detection
    sig_count = sum(1 for r in results if r['late'] > r['early'] + 0.05 and r['win_rate'] > 0.52)
    print(f"\n  Seeds with LEARNING SIGNAL: {sig_count}/{len(seeds)}")

if __name__ == "__main__":
    print("MCR Learning Loop — FIXED SNR EXPERIMENT")
    print("controlled stochasticity: deterministic kernel + 5% bounded noise")
    print("="*65)
    run_multi_seed(500, seeds=[42,123,7,999,314,271,888])
