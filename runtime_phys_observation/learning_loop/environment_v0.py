#!/usr/bin/env python3
"""MCR Learning Loop v0 — FIXED: difficulty as observable, not reward multiplier
Tests: does π(a|s) learn to choose better retrieval configs?"""
import sys, random, itertools
from dataclasses import dataclass

sys.path.insert(0, '/home/minimak/mcr/stable')

# ═══ ORACLE (external anchor) ════════════════════════════════════════════
GOLD = {
    "python_gc":        ["python_gc","docker_runtime"],
    "sql_query":         ["sql_query","file_system"],
    "docker_runtime":    ["docker_runtime","wal_replay"],
    "wal_replay":        ["wal_replay","crash_recovery"],
    "semantic_search":   ["semantic_search","network_protocol"],
    "crash_recovery":    ["crash_recovery","wal_replay"],
    "network_protocol":   ["network_protocol","file_system"],
    "file_system":       ["file_system","network_protocol"],
}
QUERIES = list(GOLD.keys())

def oracle_f1(query, retrieved):
    gold = set(GOLD.get(query, []))
    retr = set(retrieved) if retrieved else set()
    if not gold or not retr: return 0.0
    tp = len(gold & retr)
    return 2*tp/(len(gold)+len(retr))

# ═══ ACTION SPACE (36 discrete configs) ══════════════════════════════════
STRATS = ["broad","focused","semantic","random"]
FOCI   = ["working","episodic","semantic"]
BIASES = ["aggressive","normal","conservative"]
ACTION_TABLE = [{"s":s,"f":f,"b":b} for s,f,b in itertools.product(STRATS,FOCI,BIASES)]

# Focus-domain affinity (simplified world model)
FOCUS_DOMAIN = {
    "python_gc":"working","sql_query":"episodic","docker_runtime":"semantic",
    "wal_replay":"episodic","semantic_search":"semantic","crash_recovery":"episodic",
    "network_protocol":"semantic","file_system":"working",
}

# ═══ RETRIEVAL QUALITY MODEL ═════════════════════════════════════════════
# Action → true retrieval quality (noiseless base probability)
def retrieval_quality(query, action, step, total_steps):
    """Returns base probability that this action gets a relevant result.
    This is the TRUE causal relationship we're learning."""
    s,f,b = action["s"], action["f"], action["b"]
    q_topic = query
    best_focus = FOCUS_DOMAIN.get(query, "working")

    # Strategy quality
    if   s == "semantic": base = 0.75 if step == 1 else 0.60
    elif s == "focused":  base = 0.70 if step <= 2 else 0.45
    elif s == "broad":    base = 0.40  # always noisy
    else:                base = 0.20  # random: always poor

    # Focus match bonus
    if f == best_focus:   base += 0.15
    elif f != "episodic": base -= 0.05  # mild penalty for wrong focus

    # Bias has small effect
    if   b == "aggressive" and step > 1: base += 0.05
    elif b == "conservative":             base -= 0.02

    return base  # deterministic base (noise added at retrieval time)

def do_retrieve(query, action, step, total_steps):
    """Execute retrieval with noisy outcome from base quality."""
    q = query
    base = retrieval_quality(q, action, step, total_steps)
    hit = random.random() < base  # Bernoulli with quality-dependent prob
    gold_topics = QUERIES
    if hit:
        return [q] + [t for t in gold_topics if t != q and random.random() < 0.25]
    else:
        return [t for t in gold_topics if random.random() < 0.25]

# ═══ POLICY ══════════════════════════════════════════════════════════════
class Policy:
    def __init__(self, lr=0.1, rand=False):
        # 36 actions × 8 state features
        self.W = [[random.gauss(0, 0.05) for _ in range(8)] for _ in range(36)]
        self.lr, self.rand = lr, rand
        self.baseline = 0.0
    def select(self, state, eps=0.1):
        if self.rand or random.random() < eps:
            return ACTION_TABLE[int(random.random()*36)]
        scores = [sum(state[j]*self.W[i][j] for j in range(8)) for i in range(36)]
        return ACTION_TABLE[scores.index(max(scores))]
    def update(self, state, action, reward):
        idx = ACTION_TABLE.index(action)
        delta = self.lr * (reward - self.baseline)
        for j in range(8): self.W[idx][j] += delta * state[j]
        self.baseline = 0.9*self.baseline + 0.1*reward

# ═══ STATE ENCODER ══════════════════════════════════════════════════════
def encode_state(ep, total_ep, hist, diff):
    """8-dim feature vector for policy input."""
    recent = hist[-3:] if hist else []
    topics = [t for e in recent for t in (e if isinstance(e, list) else [e])]
    div = len(set(topics)) / max(len(topics), 1.0) if topics else 0.0
    hit_rate = sum(1 for e in recent if e) / max(len(recent), 1.0)
    return [
        ep / max(total_ep, 1),     # 0: time through experiment
        ep % 8 / 7.0,              # 1: position in query cycle
        div,                        # 2: retrieval diversity
        hit_rate,                   # 3: recent hit rate
        diff / 3.0,                 # 4: difficulty level
        len(recent) / 3.0,          # 5: progress through episode
        1.0 if recent else 0.0,    # 6: has history
        random.random() * 0.05,     # 7: exploration bonus
    ]

# ═══ ENVIRONMENT ════════════════════════════════════════════════════════
class Env:
    """3-step delayed reward + difficulty drift (difficulty = observable state, NOT reward multiplier)."""
    def __init__(self, steps=3):
        self.T = steps
        self.diff = 1.0
        self.episode_reward = 0.0

    def reset(self, query):
        self.episode_reward = 0.0
        return {"step": 0, "q": query, "diff": self.diff, "hist": [], "active": True}

    def step(self, state, retrieved):
        s, q, hist = state["step"], state["q"], state["hist"]
        hist = hist + [retrieved]
        done = s >= self.T - 1
        reward = 0.0

        if done:
            # Final oracle F1 on last retrieval (episode-level evaluation)
            f1 = oracle_f1(q, retrieved)
            reward = f1  # NOTE: difficulty NOT multiplied into reward
            self.episode_reward = reward
            # Drift difficulty based on success (only affects state, not reward)
            if   f1 > 0.6: self.diff = min(3.0, self.diff * 1.1)
            elif f1 < 0.2: self.diff = max(0.5, self.diff * 0.9)

        return {"step": s+1, "q": q, "diff": self.diff, "hist": hist, "active": not done}, reward, not done

# ═══ EPISODE RUNNER ═════════════════════════════════════════════════════
def run_episode(pol, env, query, eps, total_ep):
    state = env.reset(query)
    total_reward = 0.0
    while state["active"] and state["step"] < env.T:
        enc = encode_state(total_ep, 200, state["hist"], state["diff"])
        action = pol.select(enc, eps=eps)
        retrieved = do_retrieve(query, action, state["step"]+1, env.T)
        state, reward, _ = env.step(state, retrieved)
        if reward > 0:
            pol.update(enc, action, reward)
        total_reward += reward
    return total_reward

# ═══ A/B EXPERIMENT ════════════════════════════════════════════════════
def run_ab(N=200):
    print(f"{'Ep':>4} {'R_A':>7} {'R_B':>7} {'Δ':>8} {'dA':>5} {'dB':>5}  {'πA_top_actions':>30}")
    RA, RB, Deltas = [], [], []

    envA = Env(steps=3)
    envB = Env(steps=3)
    polA = Policy(lr=0.1, rand=False)
    polB = Policy(lr=0.1, rand=True)

    for ep in range(N):
        q = QUERIES[ep % len(QUERIES)]
        eps = max(0.05, 0.8 - ep/250)  # annealing: explore→exploit

        rA = run_episode(polA, envA, q, eps, ep)
        rB = run_episode(polB, envB, q, eps=1.0, total_ep=ep)
        delta = rA - rB
        RA.append(rA); RB.append(rB); Deltas.append(delta)

        if ep % 20 == 0 or ep < 5:
            top_idx = sorted(range(36), key=lambda i: max(polA.W[i]), reverse=True)[:3]
            top_acts = [f"{ACTION_TABLE[i]['s']}/{ACTION_TABLE[i]['f']}" for i in top_idx]
            print(f"{ep:>4} {rA:>7.3f} {rB:>7.3f} {delta:>+8.3f} {envA.diff:>5.2f} {envB.diff:>5.2f}  {str(top_acts):>30}")

    # ── Analysis ───────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    early = sum(Deltas[:50])/50
    late  = sum(Deltas[-50:])/50
    win   = sum(1 for d in Deltas if d > 0) / N
    print(f"Δreward:  early50={early:+.4f}  late50={late:+.4f}  trend={late-early:+.4f}")
    print(f"A wins:   {win*100:.1f}% of episodes ({win*N:.0f}/{N})")
    print(f"difficulty drift: A={envA.diff:.2f}  B={envB.diff:.2f}")
    print()
    if late > early + 0.12 and win > 0.55:
        print("→ LEARNING SIGNAL DETECTED: A significantly outperforms B over time")
    elif late < early - 0.12:
        print("→ NEGATIVE: A degrading vs B (policy bug)")
    else:
        print("→ INCONCLUSIVE: signal within noise band")

    # ── Sanity check: is difficulty drift same for both? ──────────────
    if abs(envA.diff - envB.diff) > 0.3:
        print(f"  ⚠ difficulty drift differs A={envA.diff:.2f} vs B={envB.diff:.2f}")
        print(f"  ⚠ this means environment reacts to agent quality — hard to isolate learning effect")

    return {"RA": RA, "RB": RB, "Deltas": Deltas,
            "early": early, "late": late, "win_rate": win,
            "diff_A": envA.diff, "diff_B": envB.diff}

if __name__ == "__main__":
    print("MCR Learning Loop v0 — A/B with REAL action-reward causality")
    print("="*70)
    run_ab(200)
