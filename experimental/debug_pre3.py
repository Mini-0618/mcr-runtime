import sys
sys.path.insert(0, '/home/minimak/mcr')
from semantic_governance_v19g import *

episodic = MockEpisodic()
def get_cat(i): return episodic.get_category(i)

gov = BridgeGovernanceLayer(
    gc_config=GCConfig(pre_max_age=20, gc_interval=1),
    get_category_fn=get_cat
)

for i in range(3):
    gov.try_form_bridge(f't{i}', 'food', {i, i+1})

print(f'gov.tick={gov.tick}, _last_gc={gov._last_gc}')

for i in range(3):
    gov.tick += 1
    print(f'BEFORE tick={gov.tick}: _last_gc={gov._last_gc}, interval_check={gov.tick - gov._last_gc} >= {gov.gc.gc_interval}')
    print(f'  will return early: {gov.tick - gov._last_gc < gov.gc.gc_interval}')
    pre_before = len([x for x in gov.bridges.values() if x.state == BRIDGE_STATE_PRE])
    gov.run_gc()
    pre_after = len([x for x in gov.bridges.values() if x.state == BRIDGE_STATE_PRE])
    print(f'  AFTER run_gc: _last_gc={gov._last_gc}, pre {pre_before}->{pre_after}, gc_events={len(gov.gc_events)}')
