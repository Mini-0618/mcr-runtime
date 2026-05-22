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

# Monkey-patch run_gc to trace deletion
original_run_gc = gov.run_gc.__func__

def traced_run_gc(self):
    if self.tick - self._last_gc < self.gc.gc_interval:
        return
    self._last_gc = self.tick

    to_delete = []
    print(f'  [run_gc tick={self.tick}] START, bridges={[b.id for b in self.bridges.values()]}')

    for bridge_id in list(self.bridges.keys()):
        bridge = self.bridges[bridge_id]
        bridge.last_gc_tick = self.tick

        if bridge.state == BRIDGE_STATE_COLLAPSED:
            print(f'  [run_gc] SKIP collapsed {bridge_id}')
            continue

        if bridge.state == BRIDGE_STATE_PRE:
            age = self.tick - bridge.pre_formation_tick
            print(f'  [run_gc] PRE {bridge_id}: age={age} vs pre_max_age={self.gc.pre_max_age}')
            if age > self.gc.pre_max_age:
                print(f'  [run_gc] -> DELETE {bridge_id}')
                to_delete.append(bridge_id)
                self.gc_events.append({"tick": self.tick, "bridge": bridge.id, "reason": "pre_max_age", "age": age})
            continue

    print(f'  [run_gc] to_delete: {to_delete}')
    for bid in to_delete:
        if bid in self.bridges:
            del self.bridges[bid]
            print(f'  [run_gc] DELETED {bid}')
    print(f'  [run_gc] END, remaining bridges={[b.id for b in self.bridges.values()]}')

# Apply monkey-patch at class level
import semantic_governance_v19g as sg
sg.BridgeGovernanceLayer.run_gc = traced_run_gc

# Re-create gov with patched class
gov = sg.BridgeGovernanceLayer(
    gc_config=sg.GCConfig(pre_max_age=20, gc_interval=1),
    get_category_fn=get_cat
)

for i in range(3):
    gov.try_form_bridge(f't{i}', 'food', {i, i+1})

for t in range(1, 5):
    gov.tick += 1
    print(f'=== tick={t} ===')
    gov.run_gc()
    print(f'bridges now: {[b.id for b in gov.bridges.values()]}')
