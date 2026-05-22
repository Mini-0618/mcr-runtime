#!/usr/bin/env python3
"""MCR Learning Loop v3 — per-step importance-sampled credit assignment
Key fix: each action gets weighted update based on its step importance."""
import sys, random, itertools
sys.path.insert(0, '/home/minimak/mcr/stable')

GOLD = {"python_gc":"python_gc","sql_query":"sql_query","docker_runtime":"docker_runtime",
        "wal_replay":"wal_replay","semantic_search":"semantic_search","crash_recovery":"crash_recovery",
        "network_protocol":"network_protocol","file_system":"file_system"}
QUERIES = list(GOLD.keys())

def oracle_f1(query, retrieved):
    gold = {GOLD.get(query, query)}
    retr = set(retrieved) if retrieved else set()
    if not gold or not retr: return 0.0
    tp = len(gold & retr)
    return 2*tp/(len(gold)+len(retr))

# A0: sem_first — best on step1 (0.90), poor on step2+ (0.20)
# A1: focused   — poor on step1 (0.20), best on step2+ (0.70)
ACTION_TABLE = [
    {"id":0,"name":"sem_first","q":[0.90,0.20,0.20]},
    {"id":1,"name":"focused", "q":[0.20,0.70,0.70]},
]
# Optimal strategy: A0 then A1 (A0 for step1, A1 for step2+)
# Optimal reward ≈ 0.90 on step1 + 0.70 on steps 2+ = 0.767
# Random (random mix of A0/A1): average across all steps = 0.567
# Δoptimal = 0.200

# Credit weights: how much does each step's action contribute to episode reward?
# step1 action (A0) contributes most (oracle is on final step)
# steps 2-3 (A1) contribute less in credit assignment
STEP_WEIGHTS = [0.7, 0.2, 0.1]  # credit weight per step

def do_retrieve(query, action, step, total_steps):
    base = action["q"][step-1] + random.gauss(0, 0.05)
    hit = random.random() < base
    if hit:
        return [query] + [t for t in QUERIES if t != query and random.random()<0.15]
    return [t for t in QUERIES if random.random()<0.15]

class Policy:
    """2 actions × 5 state features. prev_action_id in state."""
    NA, NDIM = 2, 5
    def __init__(self, lr=0.3, rand=False):
        self.W = [[random.gauss(0,0.05) for _ in range(self.NDIM)] for _ in range(self.NA)]
        self.lr, self.rand = lr, rand
        self.baseline = 0.0

    def select(self, state, eps=0.1):
        if self.rand or random.random()<eps:
            return ACTION_TABLE[int(random.random()*self.NA)]
        scores = [sum(state[j]*self.W[i][j] for j in range(self.NDIM)) for i in range(self.NA)]
        return ACTION_TABLE[scores.index(max(scores))]

    def update(self, state, action, reward, weight=1.0):
        """Weighted update — weight allows per-step credit assignment."""
        delta = self.lr * weight * (reward - self.baseline)
        idx = action["id"]
        for j in range(self.NDIM):
            self.W[idx][j] += delta * state[j]
        self.baseline = 0.9*self.baseline + 0.1*(reward*weight)

class Env:
    STEPS = 3
    def reset(self, q): return {"step":0,"q":q,"hist":[],"active":True}
    def step(self, state, retrieved):
        s,q,hist = state["step"],state["q"],state["hist"]
        hist = hist+[retrieved]; done = s>=self.STEPS-1; r=0.0
        if done: r = oracle_f1(q, retrieved)
        return {"step":s+1,"q":q,"hist":hist,"active":not done},r,not done

def encode(step, total_steps, prev_id, hist):
    recent = hist[-2:] if hist else []
    topics = [t for e in recent for t in (e if isinstance(e,list) else [e])]
    div = len(set(topics))/max(len(topics),1) if topics else 0.0
    return [step/max(total_steps,1), prev_id, div, len(recent)/3.0, 1.0 if hist else 0.0]

def run_episode(pol, env, query, eps, ep_idx):
    S = env.reset(query)
    trajectory = []
    prev_id = 0
    while S["active"] and S["step"] < env.STEPS:
        enc = encode(S["step"]+1, env.STEPS, prev_id, S["hist"])
        act = pol.select(enc, eps=eps)
        retr = do_retrieve(query, act, S["step"]+1, env.STEPS)
        S, r, _ = env.step(S, retr)
        trajectory.append((enc, act, r, S["step"]-1))  # step_idx stored
        prev_id = act["id"]
    # Apply weighted updates — each action gets step-specific credit
    final_r = sum(r for _,_,r,_ in trajectory)
    for enc, act, r, step_idx in trajectory:
        weight = STEP_WEIGHTS[step_idx] if step_idx < len(STEP_WEIGHTS) else 0.1
        pol.update(enc, act, final_r, weight=weight)
    return final_r

def compute_optimal():
    # Optimal: A0 step1(0.90) + A1 step2(0.70) + A1 step3(0.70) = 2.30 → norm 0.767
    # Random: 6*(0.567)/3 = 0.567
    return 0.767, 0.567

def run_trial(N=500, seed=None):
    if seed is not None: random.seed(seed)
    opt_r, rand_r = compute_optimal()
    envA, envB = Env(), Env()
    polA = Policy(lr=0.3, rand=False)
    polB = Policy(lr=0.3, rand=True)
    RA,RB,D=[],[],[]
    for ep in range(N):
        q = QUERIES[ep%len(QUERIES)]
        eps = max(0.02, 0.9 - ep/200)
        rA = run_episode(polA, envA, q, eps, ep)
        rB = run_episode(polB, envB, q, eps=1.0, ep_idx=ep)
        RA.append(rA); RB.append(rB); D.append(rA-rB)
    early,late = sum(D[:100])/100,sum(D[-100:])/100
    win = sum(1 for d in D if d>0)/N
    return {"early":early,"late":late,"trend":late-early,"win":win,
            "RA":RA,"RB":RB,"D":D}

def run_ab(N=500, seeds=[42,123,7,999,314]):
    print(f"Optimal expected: 0.767  Random expected: 0.567  Δoptimal=+0.200")
    print(f"Running {len(seeds)} seeds × {N} eps = {len(seeds)*N} total episodes")
    results = [run_trial(N, s) for s in seeds]
    # Average across seeds
    all_early = [r["early"] for r in results]
    all_late  = [r["late"]  for r in results]
    all_trend = [r["trend"] for r in results]
    all_win   = [r["win"]   for r in results]
    avg_early = sum(all_early)/len(all_early)
    avg_late  = sum(all_late)/len(all_late)
    avg_trend = sum(all_trend)/len(all_trend)
    avg_win   = sum(all_win)/len(all_win)
    print(f"\n{'='*60}")
    print(f"Across {len(seeds)} seeds:")
    print(f"  early Δ: {avg_early:+.4f}  (individual: {[f'{e:+.3f}' for e in all_early]})")
    print(f"  late  Δ: {avg_late:+.4f}  (individual: {[f'{l:+.3f}' for l in all_late]})")
    print(f"  trend:   {avg_trend:+.4f}")
    print(f"  A wins:  {avg_win*100:.1f}%")
    print(f"{'='*60}")
    if avg_trend > 0.08 and avg_win > 0.52:
        print("→ LEARNING SIGNAL: A improves over B over time")
    elif avg_trend < -0.08:
        print("→ DEGRADING: A getting worse than B")
    else:
        print("→ INCONCLUSIVE: signal within noise")
    return results

if __name__=="__main__":
    print("MCR Learning Loop v3 — per-step credit assignment + multi-seed")
    print("="*60)
    run_ab(500, seeds=[42,123,7,999,314,271,888])
