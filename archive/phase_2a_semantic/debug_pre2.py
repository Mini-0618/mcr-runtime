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

b = list(gov.bridges.values())[0]
print(f'gc_config id: {id(gov.gc)}')
print(f'bridge._gc_ref: {id(b._gc_ref) if hasattr(b, "_gc_ref") and b._gc_ref else "NOT SET"}')
print(f'bridge._gc_ref == gov.gc: {getattr(b, "_gc_ref", None) == gov.gc}')
print(f'bridge.pre_formation_tick: {b.pre_formation_tick}')
print(f'pre_max_age: {b._gc_ref.pre_max_age if hasattr(b, "_gc_ref") and b._gc_ref else "N/A"}')
print(f'bridges after form: {len(gov.bridges)}')

for i in range(3):
    gov.tick += 1
    pre_before = len([x for x in gov.bridges.values() if x.state == BRIDGE_STATE_PRE])
    gov.run_gc()
    pre_after = len([x for x in gov.bridges.values() if x.state == BRIDGE_STATE_PRE])
    print(f'tick={gov.tick}: pre {pre_before}->{pre_after}, gc_events={len(gov.gc_events)}')
    if not pre_after:
        print('All cleaned!')
        break
