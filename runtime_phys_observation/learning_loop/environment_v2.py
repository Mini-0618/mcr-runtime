#!/usr/bin/env python3
"""MCR Learning Loop v2 — prev_action in state + fixed difficulty (clean comparison)
Tests: can π learn conditional action sequence (A on step1, B on step2+)?"""
import sys, random, itertools
sys.path.insert(0, '/home/minimak/mcr/stable')

# ═══ ORACLE ════════════════════════════════════════════════════════════
GOLD = {
    "python_gc":"python_gc","sql_query":"sql_query","docker_runtime":"docker_runtime",
    "wal_replay":"wal_replay","semantic_search":"semantic_search","crash_recovery":"crash_recovery",
    "network_protocol":"network_protocol","file_system":"file_system",
}
QUERIES = list(GOLD.keys())

def oracle_f1(query, retrieved):
    gold = {GOLD.get(query, query)}
    retr = set(retrieved) if retrieved else set()
    if not gold or not retr: return 0.0
    tp = len(gold & retr)
    return 2*tp/(len(gold)+len(retr))

# ═══ ACTION SPACE — 2 actions, CLEAR quality gap ═════════════════════════
# A0: "sem_first" — optimal on step1 (0.90), poor on step2+ (0.20)
# A1: "focused"   — poor on step1 (0.20), optimal on step2+ (0.70)
ACTION_TABLE = [
    {"id":0,"name":"sem_first","step1q":0.90,"step2q":0.20},
    {"id":1,"name":"focused", "step1q":0.20,"step2q":0.70},
]

# ═══ RETRIEVAL ══════════════════════════════════════════════════════════
def retrieval_quality(query, action, step, total_steps):
    base = action["step1q"] if step == 1 else action["step2q"]
    return base + random.gauss(0, 0.05)  # tiny noise

def do_retrieve(query, action, step, total_steps):
    base = retrieval_quality(query, action, step, total_steps)
    hit = random.random() < base
    if hit:
        return [query] + [t for t in QUERIES if t != query and random.random()<0.15]
    else:
        return [t for t in QUERIES if random.random()<0.15]

# ═══ POLICY — prev_action in state! ══════════════════════════════════════
class Policy:
    """
    2 actions × 5 state features.
    Key: state includes prev_action_id so policy learns conditional sequences.
    """
    NA, NDIM = 2, 5
    def __init__(self, lr=0.3, rand=False):
        self.W = [[random.gauss(0,0.1) for _ in range(self.NDIM)] for _ in range(self.NA)]
        self.lr, self.rand = lr, rand
        self.baseline = 0.0

    def select(self, state, eps=0.1):
        if self.rand or random.random()<eps:
            return ACTION_TABLE[int(random.random()*self.NA)]
        scores = [sum(state[j]*self.W[i][j] for j in range(self.NDIM)) for i in range(self.NA)]
        return ACTION_TABLE[scores.index(max(scores))]

    def update_all(self, trajectory, total_reward):
        """
        All actions updated with the final episode reward.
        (3 steps, each action gets full episode credit)
        """
        for state, action, r in trajectory:
            delta = self.lr * (total_reward - self.baseline)
            idx = action["id"]
            for j in range(self.NDIM):
                self.W[idx][j] += delta * state[j]
        self.baseline = 0.9*self.baseline + 0.1*total_reward

# ═══ STATE ENCODER — includes prev_action_id ═════════════════════════════
def encode_state(step, total_steps, prev_action_id, hist, diff):
    """5-dim: step progress + prev_action + diversity + difficulty."""
    recent = hist[-2:] if hist else []
    topics = [t for e in recent for t in (e if isinstance(e,list) else [e])]
    div = len(set(topics))/max(len(topics),1) if topics else 0.0
    return [
        step / max(total_steps, 1),        # 0: episode progress
        prev_action_id / 1.0,             # 1: PREV ACTION (critical for conditional)
        div,                                # 2: retrieval diversity
        diff / 3.0,                        # 3: difficulty (fixed in v2)
        1.0 if hist else 0.0,             # 4: has history
    ]

# ═══ ENVIRONMENT (FIXED DIFFICULTY — both agents face identical env) ══════
class Env:
    STEPS = 3
    def __init__(self): self.diff = 1.0
    def reset(self, q): return {"step":0,"q":q,"diff":self.diff,"hist":[],"active":True}
    def step(self, state, retrieved):
        s,q,hist = state["step"],state["q"],state["hist"]
        hist = hist+[retrieved]; done = s>=self.STEPS-1; reward=0.0
        if done: reward = oracle_f1(q, retrieved)  # final oracle F1
        return {"step":s+1,"q":q,"diff":self.diff,"hist":hist,"active":not done},reward,not done

# ═══ EPISODE ══════════════════════════════════════════════════════════════
def run_episode(pol, env, query, eps, ep_idx):
    S = env.reset(query)
    trajectory = []
    prev_action_id = 1  # default to "focused" (sensible default)
    while S["active"] and S["step"] < env.STEPS:
        enc = encode_state(S["step"]+1, env.STEPS, prev_action_id, S["hist"], S["diff"])
        act = pol.select(enc, eps=eps)
        retr = do_retrieve(query, act, S["step"]+1, env.STEPS)
        S, r, _ = env.step(S, retr)
        trajectory.append((enc, act, r))
        prev_action_id = act["id"]  # carry forward
    total = sum(r for _,_,r in trajectory)
    pol.update_all(trajectory, total)
    return total

# ═══ SANITY CHECK: what is the OPTIMAL strategy? ══════════════════════════
def compute_optimal_reward():
    """What reward does optimal policy get (A0 on step1, A1 on step2+)?"""
    base = ACTION_TABLE
    # Optimal: A0(step1=0.90) → A1(step2=0.70) → A1(step3=0.70)
    # For simplicity: avg of A0.step1q and A1.step2q
    opt = (0.90 + 0.70 + 0.70) / 3.0  # ≈ 0.767
    # Random: average of all
    rand = (0.90+0.20+0.20+0.70+0.70+0.70)/6.0  # ≈ 0.567
    return opt, rand

# ═══ A/B EXPERIMENT ══════════════════════════════════════════════════════
def run_ab(N=400):
    opt_r, rand_r = compute_optimal_reward()
    print(f"Optimal policy expected reward: {opt_r:.3f}")
    print(f"Random policy expected reward:  {rand_r:.3f}")
    print(f"Expected Δ if learning:        {opt_r-rand_r:+.3f}")
    print(f"{'='*70}")

    envA, envB = Env(), Env()
    polA = Policy(lr=0.3, rand=False)
    polB = Policy(lr=0.3, rand=True)  # rand=True = pure random selection
    RA,RB,D=[],[],[]
    print(f"{'Ep':>4} {'R_A':>7} {'R_B':>7} {'Δ':>8}  {'W_A':>6}  verdict")
    for ep in range(N):
        q = QUERIES[ep%len(QUERIES)]
        eps = max(0.02, 0.9 - ep/200)  # annealing
        rA = run_episode(polA, envA, q, eps, ep)
        rB = run_episode(polB, envB, q, eps=1.0, ep_idx=ep)
        d=rA-rB; RA.append(rA); RB.append(rB); D.append(d)
        if ep%25==0 or ep<3:
            w=min(25,len(D)); avg=sum(D[-w:])/w
            # Show policy weights for each action given state (step=1, prev=A0 vs A1)
            s0_A0 = sum(polA.W[0][j]*0.33 + polA.W[0][j]*0 for j in range(5))  # step=0.33
            s0_A1 = sum(polA.W[1][j]*0.33 + polA.W[1][j]*0 for j in range(5))
            w25=sum(D[-25:])/25; w100=sum(D[-100:])/100 if len(D)>=100 else avg
            print(f"{ep:>4} {rA:>7.3f} {rB:>7.3f} {d:>+8.3f}  {w25:>+7.4f}  {w100:>+7.4f}")

    early,late = sum(D[:100])/100,sum(D[-100:])/100
    win = sum(1 for d in D if d>0)/N
    print(f"\n{'='*70}")
    print(f"Δreward: early100={early:+.4f}  late100={late:+.4f}  trend={late-early:+.4f}")
    print(f"A wins:  {win*100:.1f}% ({int(win*N)}/{N})")
    print(f"env A/B difficulty: {envA.diff:.2f} / {envB.diff:.2f}  (should be 1.00/1.00)")
    if late>early+0.10 and win>0.55:
        print("→ LEARNING SIGNAL DETECTED")
    elif late<early-0.10:
        print("→ POLICY DEGRADING")
    else:
        print("→ INCONCLUSIVE")
    return RA,RB,D

if __name__=="__main__":
    print("MCR Learning Loop v2 — prev_action state + fixed difficulty")
    print("="*70)
    run_ab(400)
