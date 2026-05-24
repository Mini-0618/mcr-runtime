#!/usr/bin/env python3
"""MCR Learning Loop v1 — Fixed credit assignment + large action gap
Tests: can π(a|s) learn the optimal 3-step retrieval strategy?"""
import sys, random, itertools
sys.path.insert(0, './stable')

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

# ═══ ACTION SPACE (3 configs — large quality gap) ════════════════════════
# Only 3 actions, LARGE quality gap so learning signal is clear:
# A0: "semantic_first" — best on step1, poor on step2+  (optimal = BEST)
# A1: "focused_step2"  — ok on step2, poor on step1      (suboptimal)
# A2: "random"         — poor everywhere                 (worst)
ACTION_TABLE = [
    {"id":0,"name":"semantic_first","s":"semantic","f":"semantic","b":"aggressive"},
    {"id":1,"name":"focused_step2", "s":"focused", "f":"episodic","b":"normal"},
    {"id":2,"name":"random",        "s":"random",  "f":"working", "b":"conservative"},
]

def retrieval_quality(query, action, step, total_steps):
    """LARGE gap: optimal vs suboptimal are clearly separated."""
    s, step_i = action["s"], step
    if   s == "semantic" and step_i == 1: return 0.90  # optimal: best on first step
    elif s == "semantic":                  return 0.25  # poor on later steps
    elif s == "focused"  and step_i >= 2: return 0.65  # decent on step 2+
    elif s == "focused":                   return 0.20  # poor on step 1
    else:                                  return 0.15  # random always bad

def do_retrieve(query, action, step, total_steps):
    base = retrieval_quality(query, action, step, total_steps)
    hit = random.random() < base
    if hit:
        return [query] + [t for t in QUERIES if t != query and random.random()<0.2]
    else:
        return [t for t in QUERIES if random.random()<0.2]

# ═══ POLICY ════════════════════════════════════════════════════════════
class Policy:
    """3 actions × 6 state features. Simple linear model."""
    NA, NDIM = 3, 6
    def __init__(self, lr=0.2, rand=False):
        self.W = [[random.gauss(0,0.05) for _ in range(self.NDIM)] for _ in range(self.NA)]
        self.lr, self.rand = lr, rand
        self.baseline = 0.0

    def select(self, state, eps=0.1):
        if self.rand or random.random()<eps:
            return ACTION_TABLE[int(random.random()*self.NA)]
        scores = [sum(state[j]*self.W[i][j] for j in range(self.NDIM)) for i in range(self.NA)]
        return ACTION_TABLE[scores.index(max(scores))]

    def update_all(self, trajectory, rewards):
        """
        Update ALL actions in trajectory with discounted rewards.
        trajectory: list of (state, action, step_reward)
        rewards: list of rewards received at each step
        Corrects the credit assignment bug from v0.
        """
        T = len(trajectory)
        for t, (state, action, r_t) in enumerate(trajectory):
            # Discount factor: earlier steps get credit for future rewards
            G_t = sum(rewards[t:] )  # undiscounted (short episodes)
            delta = self.lr * (G_t - self.baseline)
            idx = action["id"]
            for j in range(self.NDIM):
                self.W[idx][j] += delta * state[j]
        if rewards:
            self.baseline = 0.9*self.baseline + 0.1*sum(rewards)/len(rewards)

# ═══ STATE ENCODER ══════════════════════════════════════════════════════
def encode_state(ep, hist, diff):
    """6-dim: step progress + retrieval diversity + difficulty."""
    recent = hist[-3:] if hist else []
    topics = [t for e in recent for t in (e if isinstance(e,list) else [e])]
    div = len(set(topics))/max(len(topics),1) if topics else 0.0
    return [
        (len(hist)+1)/5.0,   # 0: episode progress (steps taken)
        div,                  # 1: retrieval diversity
        len(recent)/3.0,      # 2: recent action count
        diff/3.0,             # 3: difficulty (observable)
        ep%8/7.0,            # 4: query position in cycle
        1.0 if hist else 0.0, # 5: has history
    ]

# ═══ ENVIRONMENT ════════════════════════════════════════════════════════
class Env:
    """3-step task. Reward ONLY at episode end. Difficulty = observable, NOT reward."""
    STEPS = 3
    def __init__(self): self.diff = 1.0
    def reset(self, q): return {"step":0,"q":q,"diff":self.diff,"hist":[],"active":True}
    def step(self, state, retrieved):
        s,q,hist = state["step"],state["q"],state["hist"]
        hist = hist+[retrieved]
        done = s>=self.STEPS-1; reward=0.0
        if done:
            reward = oracle_f1(q, retrieved)
            if   reward>0.6: self.diff = min(3.0, self.diff*1.1)
            elif reward<0.2: self.diff = max(0.5, self.diff*0.9)
        return {"step":s+1,"q":q,"diff":self.diff,"hist":hist,"active":not done},reward,not done

# ═══ EPISODE ═════════════════════════════════════════════════════════════
def run_episode(pol, env, query, eps, ep_idx):
    S = env.reset(query)
    trajectory, step_rewards = [], []
    while S["active"] and S["step"] < env.STEPS:
        enc = encode_state(ep_idx, S["hist"], S["diff"])
        act = pol.select(enc, eps=eps)
        retr = do_retrieve(query, act, S["step"]+1, env.STEPS)
        S, r, _ = env.step(S, retr)
        trajectory.append((enc, act, r))
        step_rewards.append(r)
    # Update ALL actions with full episode reward
    pol.update_all(trajectory, step_rewards)
    return sum(step_rewards)  # total episode reward

# ═══ A/B EXPERIMENT ════════════════════════════════════════════════════
def run_ab(N=300):
    envA, envB = Env(), Env()
    polA = Policy(lr=0.2, rand=False)
    polB = Policy(lr=0.2, rand=True)
    RA,RB,D=[],[],[]
    print(f"{'Ep':>4} {'R_A':>7} {'R_B':>7} {'Δ':>8} {'dA':>5} {'dB':>5}  {'πA_best':>20}  verdict")
    for ep in range(N):
        q = QUERIES[ep%len(QUERIES)]
        eps = max(0.02, 0.9 - ep/200)
        rA = run_episode(polA, envA, q, eps, ep)
        rB = run_episode(polB, envB, q, eps=1.0, ep_idx=ep)
        d=rA-rB; RA.append(rA); RB.append(rB); D.append(d)
        if ep%20==0 or ep<3:
            top=sorted(range(Policy.NA), key=lambda i: max(polA.W[i]), reverse=True)
            top_names="/".join([ACTION_TABLE[i]["name"] for i in top])
            w=min(20,len(D)); avg=sum(D[-w:])/w
            print(f"{ep:>4} {rA:>7.3f} {rB:>7.3f} {d:>+8.3f} {envA.diff:>5.2f} {envB.diff:>5.2f}  {top_names:>20}  {avg:>+.4f}")

    early,late = sum(D[:75])/75,sum(D[-75:])/75
    win = sum(1 for d in D if d>0)/N
    print(f"\n{'='*70}")
    print(f"Δreward: early={early:+.4f}  late={late:+.4f}  trend={late-early:+.4f}")
    print(f"A wins:  {win*100:.1f}% ({int(win*N)}/{N})")
    if late>early+0.15 and win>0.6:
        print("→ LEARNING SIGNAL: A significantly outperforms B")
    elif late<early-0.15:
        print("→ POLICY DEGRADING")
    else:
        print("→ INCONCLUSIVE")
    return RA,RB,D,envA.diff,envB.diff

if __name__=="__main__":
    print("MCR Learning Loop v1 — Fixed credit assignment + large action gap")
    print("="*70)
    RA,RB,D,dA,dB = run_ab(300)
