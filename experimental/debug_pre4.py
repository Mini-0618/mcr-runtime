import sys
sys.path.insert(0, '.')
from semantic_governance_v19g import *

episodic = MockEpisodic()
def get_cat(i): return episodic.get_category(i)

gov = BridgeGovernanceLayer(
    gc_config=GCConfig(pre_max_age=20, gc_interval=1),
    get_category_fn=get_cat
)

for i in range(3):
    gov.try_form_bridge(f't{i}', 'food', {i, i+1})

print(f'Created at tick={gov.tick}')
b = list(gov.bridges.values())[0]
print(f'pre_formation_tick={b.pre_formation_tick}, state={b.state}')

for t in range(1, 25):
    gov.tick += 1
    gc_fired_this_tick = gov.tick - gov._last_gc >= gov.gc.gc_interval

    # Manually trace the PRE branch
    for bid, br in gov.bridges.items():
        if br.state == BRIDGE_STATE_PRE:
            age = gov.tick - br.pre_formation_tick
            if age > gov.gc.pre_max_age:
                print(f'  [tick={gov.tick}] bridge {bid}: age={age} > pre_max_age={gov.gc.pre_max_age} -> SHOULD DELETE')

    gov.run_gc()
    pre_after = len([x for x in gov.bridges.values() if x.state == BRIDGE_STATE_PRE])
    gc_total = len(gov.gc_events)
    print(f'tick={gov.tick}: pre={pre_after}, total_gc_events={gc_total}')

    if not pre_after:
        print('ALL CLEANED!')
        break
