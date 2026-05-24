#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from semantic_governance_v19g import *

episodic = MockEpisodic()
def get_cat(item_id):
    return episodic.get_category(item_id)

gov = BridgeGovernanceLayer(
    gc_config=GCConfig(pre_max_age=15, gc_interval=5),
    get_category_fn=get_cat,
)

# Create 3 pre-bridges
for i in range(3):
    gov.try_form_bridge(f'test_{i}', 'food', {i, i+1})

print(f'gov.tick={gov.tick}, bridges={len(gov.bridges)}')
for b in gov.bridges.values():
    print(f'  {b.id}: state={b.state}, pre_formation_tick={b.pre_formation_tick}, age={gov.tick - b.pre_formation_tick}')

# Advance tick by tick
for t in range(1, 21):
    gov.tick += 1
    pre_before = len([b for b in gov.bridges.values() if b.state == BRIDGE_STATE_PRE])
    gov.run_gc()
    pre_after = len([b for b in gov.bridges.values() if b.state == BRIDGE_STATE_PRE])
    gc_fired = len(gov.gc_events)
    print(f'tick={gov.tick}: pre_before={pre_before}, pre_after={pre_after}, total_gc_events={gc_fired}')
    if not pre_after:
        print('All pre-bridges cleaned!')
        break
