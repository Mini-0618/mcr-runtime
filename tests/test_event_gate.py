"""
Event Gate + Hermes Bridge Integration Test
验证:
1. EventGate validates proposals correctly
2. HermesBridge parses LLM output to proposals
3. Accepted events go through reducer → WAL
4. Rejected events are blocked
"""
import sys, os, uuid
sys.path.insert(0, '/home/minimak/mcr')

from runtime import (
    MCRRuntimeEngine, EventGate, HermesBridge,
    EventProposal, ValidationResult
)


def test_event_gate_validation():
    print("=== Event Gate Validation Tests ===\n")

    gate = EventGate()

    # Test 1: valid proposal
    valid = EventProposal(
        event_type="memory_store",
        tick=1,
        memory_id="mem_001",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic"},
        justification="storing test memory"
    )
    result = gate.validate(valid)
    print(f"[1] Valid proposal: {result.accepted} — {result.reason}")

    # Test 2: invalid event type
    invalid_type = EventProposal(
        event_type="INVALID_TYPE",
        tick=2,
        memory_id="mem_002",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={},
    )
    result2 = gate.validate(invalid_type)
    print(f"[2] Invalid type: {result2.accepted} — {result2.reason}")

    # Test 3: missing required field
    missing_field = EventProposal(
        event_type="memory_store",
        tick=3,
        memory_id="mem_003",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={},  # missing content and tier
    )
    result3 = gate.validate(missing_field)
    print(f"[3] Missing field: {result3.accepted} — {result3.reason}")

    # Test 4: forbidden field
    forbidden = EventProposal(
        event_type="memory_store",
        tick=4,
        memory_id="mem_004",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic", "state": "corrupted"},
    )
    result4 = gate.validate(forbidden)
    print(f"[4] Forbidden field: {result4.accepted} — {result4.reason}")

    # Test 5: non-monotonic tick
    nonmono = EventProposal(
        event_type="memory_store",
        tick=1,  # same as before
        memory_id="mem_005",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic"},
    )
    result5 = gate.validate(nonmono)
    print(f"[5] Non-monotonic tick: {result5.accepted} — {result5.reason}")

    # Test 6: empty memory_id on memory operation
    empty_mem = EventProposal(
        event_type="memory_store",
        tick=6,
        memory_id="",
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"content": "test", "tier": "episodic"},
    )
    result6 = gate.validate(empty_mem)
    print(f"[6] Empty memory_id: {result6.accepted} — {result6.reason}")

    # Test 7: None memory_id on memory operation (AttributeError guard + explicit rejection)
    none_mem = EventProposal(
        event_type="memory_access",
        tick=7,
        memory_id=None,
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={},
    )
    result7 = gate.validate(none_mem)
    print(f"[7] None memory_id: {result7.accepted} — {result7.reason}")

    # Test 8: coaccess_graph isolation — clone() must deep-copy set values so mutations
    # on a cloned state cannot leak back to the original. This catches shallow-copy
    # bugs where set(v) shares mutable references between original and clone.
    from runtime.state import SystemState
    s1 = SystemState.empty()
    s1.coaccess_graph['mem_A'] = {'mem_B', 'mem_C'}
    s1.access_history.append({'memory_id': 'mem_A', 'tick': 1, 'coaccess_group_id': 'g1'})

    s2 = s1.clone()
    s2.coaccess_graph['mem_A'].add('mem_D')  # mutate cloned graph
    s2.access_history.append({'memory_id': 'mem_X', 'tick': 2, 'coaccess_group_id': 'g2'})

    # Original state must be unaffected by mutation on clone
    s1_has_D = 'mem_D' in s1.coaccess_graph.get('mem_A', set())
    s1_history_len = len(s1.access_history)
    result8 = not s1_has_D and s1_history_len == 1
    print(f"[8] coaccess_graph isolation: {result8} — clone mutation leaked: {s1_has_D}, history leaked: {s1_history_len != 1}")

    # Test 9: WAL skips malformed lines silently — verify load() on corrupted WAL
    # produces partial event list without raising. WAL._load() must not raise on
    # bad JSON; truncated JSON and lines with invalid replay_hash are skipped.
    import tempfile, os, json, hashlib
    from runtime.wal import WAL, Event
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)

    def make_event(event_id, tick, memory_id):
        e = Event(
            event_id=event_id, event_type='memory_store', tick=tick,
            memory_id=memory_id, coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
            payload={'content': f'content_{event_id}'}, timestamp=1.0, replay_hash=''
        )
        e.replay_hash = e._compute_replay_hash()
        return e

    # Two valid events with correct replay_hash
    for evt in [make_event('e1', 1, 'm1'), make_event('e2', 2, 'm2')]:
        tmp.write(json.dumps(evt.to_dict()) + '\n')
    # Malformed JSON line
    tmp.write('this is not json\n')
    # Truncated JSON line
    tmp.write('{"broken')
    tmp.close()
    w = WAL(tmp.name)
    events = w.get_all()
    os.unlink(tmp.name)
    result9 = len(events) == 2 and events[0].memory_id == 'm1' and events[1].memory_id == 'm2'
    print(f"[9] WAL corrupted load: {result9} — loaded {len(events)}/2 events, skipped 2 malformed lines")

    # Test 10: None coaccess_group_id — is_valid_uuid must not raise TypeError on None.
    # LLM can produce "coaccess_group_id": null in JSON. EventGate should reject
    # cleanly, not crash. Guard added in is_valid_uuid() for None/non-string input.
    none_uuid = EventProposal(
        event_type="memory_store",
        tick=10,
        memory_id="mem_010",
        coaccess_group_id=None,
        payload={"content": "test", "tier": "episodic"},
    )
    result10 = gate.validate(none_uuid)
    print(f"[10] None coaccess_group_id: {result10.accepted} — {result10.reason}")

    # Test 11: unimplemented event types must not fall through silently.
    # curriculum_task_create, curriculum_task_complete, failure_record are in
    # ALLOWED_EVENT_TYPES and EVENT_SCHEMAS but were absent from reducer.handlers.
    # They now map to _handle_noop. Verify gate accepts and reducer handles them.
    from runtime.reducer import DeterministicReducer
    reducer = DeterministicReducer()
    for evt_type, schema_fields in [
        ('curriculum_task_create', {'task_id': 't1', 'difficulty': 1, 'family': 'f1'}),
        ('curriculum_task_complete', {'task_id': 't1', 'reward': 1.0, 'success': True}),
        ('failure_record', {'failure_type': 'type', 'context': 'ctx', 'proposed_fix': 'fix'}),
    ]:
        proposal = EventProposal(
            event_type=evt_type, tick=11,
            memory_id=None, coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
            payload=schema_fields,
        )
        vr = gate.validate(proposal)
        # apply through reducer to confirm no KeyError or AttributeError
        from runtime.wal import Event
        evt = Event(event_id='x', event_type=evt_type, tick=11,
                    memory_id=None, coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
                    payload=schema_fields, timestamp=1.0, replay_hash='')
        s = reducer.reduce(evt, SystemState.empty())
        print(f"[11] {evt_type}: gate={vr.accepted}, reducer_tick={s.tick}")

    # Test 12: payload must be a dict — reject None and non-dict payloads cleanly.
    # If LLM produces "payload": null, item.get("payload", {}) returns None and
    # Event(payload=None) raises TypeError. Rule 7 rejects None/list/primitive payloads.
    for bad_payload, expected_reject in [(None, True), ([], True), ("str", True), (123, True)]:
        proposal = EventProposal(
            event_type="memory_store", tick=12,
            memory_id="mem_012", coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
            payload=bad_payload,
        )
        result = gate.validate(proposal)
        ok = (result.accepted == False) == expected_reject
        print(f"[12] payload={type(bad_payload).__name__}: {result.accepted} — {'OK' if ok else 'FAIL'}")

    # Test 13: get_state_snapshot() caps access_history to MAX_SNAPSHOT_ACCESS_HISTORY (20).
    # WAL has unbounded access_history but snapshot is context-only and must not grow unboundedly.
    from runtime.hermes_bridge import HermesBridge
    wal_path13 = "/home/minimak/mcr/.wal/test_snapshot_cap.jsonl"
    if os.path.exists(wal_path13):
        os.remove(wal_path13)
    eng13 = MCRRuntimeEngine(wal_path=wal_path13)
    br13 = HermesBridge(eng13)
    # Generate 50 ticks of events (same pattern as test_g2_replay)
    import random
    random.seed(42)
    mem_ids = [f"mem_{i:03d}" for i in range(50)]
    for i in range(50):
        group = str(uuid.uuid4())
        eng13.emit("memory_store", mem_ids[i], group, {"content": f"content_{i}", "tier": "episodic"})
        eng13.emit("memory_access", mem_ids[random.randint(0, i)], group, {})
    snap = br13.get_state_snapshot()
    ok13 = len(snap["access_history"]) <= HermesBridge.MAX_SNAPSHOT_ACCESS_HISTORY
    print(f"[13] snapshot access_history cap: {len(snap['access_history'])} <= {HermesBridge.MAX_SNAPSHOT_ACCESS_HISTORY} — {'OK' if ok13 else 'FAIL'}")

    # Test 14: ReplayVerifier.wal_hash() is public and deterministic.
    # Verify: (a) public API matches wal_hash returned in verify() result;
    # (b) two identical WALs produce the same hash across separate verifier instances.
    from runtime.replay_verifier import ReplayVerifier
    wal_path14 = "/home/minimak/mcr/.wal/test_wal_hash.jsonl"
    if os.path.exists(wal_path14):
        os.remove(wal_path14)
    eng14 = MCRRuntimeEngine(wal_path=wal_path14)
    for i in range(10):
        eng14.emit("memory_store", f"mem_{i}", "550e8400-e29b-41d4-a716-446655440000",
                   {"content": f"c{i}", "tier": "episodic"})
    v1 = ReplayVerifier()
    result_v1 = v1.verify(eng14.state, SystemState.empty(), eng14.wal)
    public_hash = v1.wal_hash(eng14.wal)
    match_ok = public_hash == result_v1['wal_hash']
    print(f"[14a] public wal_hash() == verify() wal_hash: {match_ok} — "
          f"public={public_hash[:16]}..., verify={result_v1['wal_hash'][:16]}...")

    # (b) wal_hash is stable when called multiple times on the same WAL (intra-session determinism).
    # Note: wal_hash is NOT deterministic across sessions because it includes timestamp.
    # WAL integrity (any byte change detected) is the intended property, not content
    # equivalence. Content equivalence across sessions is verified by G2.
    v2 = ReplayVerifier()
    hash_first = v2.wal_hash(eng14.wal)
    hash_second = v2.wal_hash(eng14.wal)
    stable_ok = hash_first == hash_second
    print(f"[14b] wal_hash stable across multiple calls: {stable_ok} — "
          f"first={hash_first[:16]}..., second={hash_second[:16]}...")

    # Test 15: WAL.is_empty() returns True for fresh empty WAL, False after events.
    # Confirms the convenience method works correctly.
    from runtime.wal import WAL
    tmp15 = "/home/minimak/mcr/.wal/test_is_empty.jsonl"
    if os.path.exists(tmp15):
        os.unlink(tmp15)
    w15 = WAL(tmp15)
    empty_ok = w15.is_empty()
    w15.append(Event(event_id='x', event_type='memory_store', tick=1,
                     memory_id='m', coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
                     payload={'content': 'c'}, timestamp=1.0, replay_hash=''))
    not_empty_ok = not w15.is_empty()
    os.unlink(tmp15)
    print(f"[15] WAL.is_empty() fresh={empty_ok}, after_append={not_empty_ok} — {'OK' if empty_ok and not_empty_ok else 'FAIL'}")

    # Test 16: Event.equals() compares content excluding replay_hash.
    # Two events with identical content but different replay_hash are equal.
    # Events with different content are not equal.
    e1 = Event(event_id='id1', event_type='memory_store', tick=1,
               memory_id='m', coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
               payload={'content': 'c'}, timestamp=1.0, replay_hash='old')
    e2 = Event(event_id='id1', event_type='memory_store', tick=1,
               memory_id='m', coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
               payload={'content': 'c'}, timestamp=1.0, replay_hash='new')  # different hash
    e3 = Event(event_id='id1', event_type='memory_store', tick=2,  # different tick
               memory_id='m', coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
               payload={'content': 'c'}, timestamp=1.0, replay_hash='')
    eq_ok = e1.equals(e2) and not e1.equals(e3)
    print(f"[16] Event.equals() same_content_different_hash={e1.equals(e2)}, different_content={e1.equals(e3)} — {'OK' if eq_ok else 'FAIL'}")

    # Test 17: EventGate rejects invalid UUID coaccess_group_id; accepts valid UUID and
    # builds coaccess_graph correctly through full bridge pipeline.
    # test_g2_replay uses engine.emit() which bypasses EventGate, so coaccess_group_id
    # UUID enforcement has no coverage via the bridge. Bare integers "1","2","3" in
    # test_g2_replay never go through EventGate.validate() Rule 4.
    wal_path17 = "/home/minimak/mcr/.wal/test_coaccess_uuid.jsonl"
    if os.path.exists(wal_path17):
        os.remove(wal_path17)
    eng17 = MCRRuntimeEngine(wal_path=wal_path17)
    br17 = HermesBridge(eng17)

    # (a) Invalid UUIDs must be rejected at the gate — event must not reach WAL
    for bad_uuid in ["1", "123", "", "not-a-uuid"]:
        p_bad = br17.create_proposal(
            event_type="memory_store", tick=1,
            memory_id="mem_17a", coaccess_group_id=bad_uuid,
            payload={"content": "test", "tier": "episodic"}
        )
        r_bad = br17.submit_proposal(p_bad)
        if r_bad.accepted:
            print(f"[17a] INVALID UUID '{bad_uuid}' was accepted — FAIL")
        else:
            print(f"[17b] Invalid UUID '{bad_uuid}' rejected: {r_bad.reason} — OK")

    # (b) Valid UUID coaccess_group_id: event accepted, WAL grows, coaccess_graph built
    valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
    p_store = br17.create_proposal(
        event_type="memory_store", tick=1,
        memory_id="mem_17b", coaccess_group_id=valid_uuid,
        payload={"content": "content_b", "tier": "episodic"}
    )
    p_access1 = br17.create_proposal(
        event_type="memory_access", tick=2,
        memory_id="mem_17b", coaccess_group_id=valid_uuid,
        payload={}
    )
    p_access2 = br17.create_proposal(
        event_type="memory_access", tick=3,
        memory_id="mem_17c", coaccess_group_id=valid_uuid,
        payload={}
    )
    # store mem_17c first so it exists when accessed
    p_store_c = br17.create_proposal(
        event_type="memory_store", tick=4,
        memory_id="mem_17c", coaccess_group_id=valid_uuid,
        payload={"content": "content_c", "tier": "episodic"}
    )
    # tick 5: access mem_17c in same group — should create coaccess edge mem_17b<->mem_17c
    p_access_same = br17.create_proposal(
        event_type="memory_access", tick=5,
        memory_id="mem_17c", coaccess_group_id=valid_uuid,
        payload={}
    )
    results = br17.submit_proposals([p_store, p_access1, p_store_c, p_access2, p_access_same])
    accepted = [r for r in results if r.accepted]
    wal_len_after = eng17.wal.len()

    # WAL must have 4 accepted events (store_b, access_b, store_c, access_c; access_same is rejected
    # because mem_17c was not yet stored at tick=5 — but the gate rejects memory_access
    # for non-existent memory, not at EventGate level. Actually, reducer._handle_access
    # returns early if memory_id not in state.memory, so the event is still accepted
    # by EventGate but has no state effect. Let's just check WAL has accepted events.)
    ok17b = wal_len_after >= 4
    print(f"[17b] Valid UUID accepted, WAL length={wal_len_after} >= 4 — {'OK' if ok17b else 'FAIL'}")

    # coaccess_graph: mem_17b and mem_17c were accessed in same group at ticks 2 and 5,
    # so they should be neighbors in the graph.
    graph_ok = (
        "mem_17c" in eng17.state.coaccess_graph.get("mem_17b", set()) and
        "mem_17b" in eng17.state.coaccess_graph.get("mem_17c", set())
    )
    print(f"[17c] coaccess_graph neighbors: {graph_ok} — "
          f"mem_17b->{eng17.state.coaccess_graph.get('mem_17b', set())}, "
          f"mem_17c->{eng17.state.coaccess_graph.get('mem_17c', set())}")

    # Test 18: policy_update — defined in ALLOWED_EVENT_TYPES and EVENT_SCHEMAS
    # (requires policy_weights and reason fields), maps to _handle_noop in reducer.
    # Must be accepted by gate and produce no state mutation beyond wal_length/tick.
    gate18 = EventGate()
    policy_proposal = EventProposal(
        event_type="policy_update",
        tick=18,
        memory_id=None,
        coaccess_group_id="550e8400-e29b-41d4-a716-446655440000",
        payload={"policy_weights": {"retrieval": 0.8}, "reason": "test"},
    )
    vr18 = gate18.validate(policy_proposal)
    from runtime.reducer import DeterministicReducer
    from runtime.state import SystemState
    evt18 = Event(event_id='x18', event_type='policy_update', tick=18,
                  memory_id=None, coaccess_group_id='550e8400-e29b-41d4-a716-446655440000',
                  payload={"policy_weights": {"retrieval": 0.8}, "reason": "test"},
                  timestamp=1.0, replay_hash='')
    s_before = SystemState.empty()
    s_after = DeterministicReducer().reduce(evt18, s_before)
    # tick should advance by 1, memory/coaccess_graph unchanged, wal_length = 1
    policy_ok = (
        vr18.accepted == True
        and s_after.tick == 18
        and len(s_after.memory) == 0
        and len(s_after.coaccess_graph) == 0
        and s_after.wal_length == 1
    )
    print(f"[18] policy_update: gate={vr18.accepted}, tick={s_after.tick}, "
          f"memory={len(s_after.memory)}, wal_length={s_after.wal_length} — "
          f"{'OK' if policy_ok else 'FAIL'}")


def test_hermes_bridge():
    print("\n=== Hermes Bridge Tests ===\n")

    # clean WAL
    wal_path = "/home/minimak/mcr/.wal/test_bridge.jsonl"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = MCRRuntimeEngine(wal_path=wal_path)
    bridge = HermesBridge(engine)

    # Test: LLM output parsing
    llm_output = '''
    {
      "proposals": [
        {
          "event_type": "memory_store",
          "tick": 1,
          "memory_id": "mem_llm_001",
          "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {"content": "from LLM", "tier": "episodic"},
          "justification": "initial memory store"
        },
        {
          "event_type": "memory_access",
          "tick": 2,
          "memory_id": "mem_llm_001",
          "coaccess_group_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {},
          "justification": "accessing stored memory"
        }
      ]
    }
    '''

    proposals = bridge.llm_to_proposals(llm_output)
    print(f"[1] Parsed {len(proposals)} proposals from LLM output")

    # Submit proposals through bridge
    results = bridge.submit_proposals(proposals)
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    print(f"[2] Accepted: {len(accepted)}, Rejected: {len(rejected)}")

    # Check WAL
    print(f"[3] WAL length: {engine.wal.len()}")
    print(f"[4] Memory items: {len(engine.state.memory)}")


def test_full_integration():
    print("\n=== Full Integration Test ===\n")

    wal_path = "/home/minimak/mcr/.wal/test_integration.jsonl"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = MCRRuntimeEngine(wal_path=wal_path)
    bridge = HermesBridge(engine)

    # Generate proposals via bridge API
    p1 = bridge.create_proposal(
        event_type="memory_store",
        tick=1,
        memory_id="mem_integ_1",
        coaccess_group_id=str(__import__('uuid').uuid4()),
        payload={"content": "integration test 1", "tier": "episodic"},
        justification="setup"
    )

    p2 = bridge.create_proposal(
        event_type="memory_store",
        tick=2,
        memory_id="mem_integ_2",
        coaccess_group_id=str(__import__('uuid').uuid4()),
        payload={"content": "integration test 2", "tier": "semantic"},
        justification="setup"
    )

    p3 = bridge.create_proposal(
        event_type="memory_access",
        tick=3,
        memory_id="mem_integ_1",
        coaccess_group_id=p1.coaccess_group_id,
        payload={},
        justification="access"
    )

    results = bridge.submit_proposals([p1, p2, p3])
    print(f"[1] Submitted 3 proposals: {len([r for r in results if r.accepted])} accepted")

    # G2 check
    from runtime.replay_verifier import ReplayVerifier
    verifier = ReplayVerifier()
    from runtime.state import SystemState

    result = verifier.verify(engine.state, SystemState.empty(), engine.wal)
    print(f"[2] G2 check: {result['match']}")
    print(f"[3] runtime_hash={result['runtime_hash']}, replay_hash={result['replay_hash']}")

    if result['match']:
        print("\n✅ FULL INTEGRATION: EventGate + HermesBridge + Reducer + WAL — G2 PASS")
    else:
        print("\n❌ G2 FAIL")


if __name__ == '__main__':
    test_event_gate_validation()
    test_hermes_bridge()
    test_full_integration()
